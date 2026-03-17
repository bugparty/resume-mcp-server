"""
Filesystem abstraction layer using PyFilesystem2.

This module provides a unified interface for file operations across local,
memory, and S3 backends.
"""

from __future__ import annotations

from typing import Optional, Any
import os
import warnings
from pathlib import Path
from urllib.parse import urlparse
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
    module="pkg_resources",
)

warnings.filterwarnings(
    "ignore",
    message="Deprecated call to `pkg_resources.declare_namespace",
    category=DeprecationWarning,
    module="pkg_resources",
)

from fs.base import FS
from fs.osfs import OSFS
from fs.memoryfs import MemoryFS


def _join_fs_url(base_url: str, child: str) -> str:
    """Join a backend URL/path with a child segment."""
    if base_url.startswith(("s3://", "mem://")):
        return f"{base_url.rstrip('/')}/{child.strip('/')}"
    return str(Path(base_url) / child)


def _s3_open_kwargs() -> dict[str, Any]:
    """Build kwargs for fs-s3fs opener from project and AWS env aliases."""
    kwargs: dict[str, Any] = {}

    endpoint_url = os.getenv("RESUME_S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL")
    region = os.getenv("RESUME_S3_REGION") or os.getenv("AWS_REGION")
    access_key_id = (
        os.getenv("RESUME_S3_ACCESS_KEY_ID")
        or os.getenv("RESUME_S3_ACCESS_KEY")
        or os.getenv("S3_ACCESS_KEY_ID")
        or os.getenv("AWS_ACCESS_KEY_ID")
    )
    secret_access_key = (
        os.getenv("RESUME_S3_SECRET_ACCESS_KEY")
        or os.getenv("RESUME_S3_SECRET_KEY")
        or os.getenv("S3_SECRET_ACCESS_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if region:
        kwargs["region"] = region
    if access_key_id:
        kwargs["aws_access_key_id"] = access_key_id
    if secret_access_key:
        kwargs["aws_secret_access_key"] = secret_access_key

    return kwargs


def create_filesystem(fs_url: str) -> FS:
    """
    Create a filesystem instance based on the provided URL.
    
    Args:
         fs_url: Filesystem URL. Supported formats:
             - Local path: "/path/to/directory"
             - Memory filesystem: "mem://" (for testing)
             - S3: "s3://bucket/path" (requires fs-s3fs)
    
    Returns:
        FS: A PyFilesystem2 filesystem instance
        
    Raises:
        ValueError: For invalid URLs
    """
    if not fs_url:
        raise ValueError("Filesystem URL cannot be empty")
        
    if fs_url.startswith("s3://"):
        try:
            # Ensure S3 opener is registered for `open_fs("s3://...")`.
            from fs_s3fs import S3FS
        except ImportError as exc:
            raise RuntimeError(
                "S3 filesystem support requires package 'fs-s3fs'. "
                "Install it with: uv add fs-s3fs"
            ) from exc

        parsed = urlparse(fs_url)
        bucket_name = parsed.netloc
        if not bucket_name:
            raise ValueError(f"Invalid S3 filesystem URL: {fs_url}")
        dir_path = parsed.path or "/"

        return S3FS(bucket_name=bucket_name, dir_path=dir_path, **_s3_open_kwargs())
    elif fs_url.startswith("mem://"):
        # Memory filesystem for testing
        return MemoryFS()
    else:
        # Local filesystem - treat as directory path
        return OSFS(fs_url, create=True)


# Global filesystem instances
_resume_fs: Optional[FS] = None
_jd_fs: Optional[FS] = None
_output_fs: Optional[FS] = None


def get_resume_fs() -> FS:
    """Get the resume filesystem instance."""
    if _resume_fs is None:
        raise RuntimeError("Resume filesystem not initialized. Call init_filesystems() first.")
    return _resume_fs


def get_jd_fs() -> FS:
    """Get the job description filesystem instance."""
    if _jd_fs is None:
        raise RuntimeError("JD filesystem not initialized. Call init_filesystems() first.")
    return _jd_fs


def get_output_fs() -> FS:
    """Get the output filesystem instance."""
    if _output_fs is None:
        raise RuntimeError("Output filesystem not initialized. Call init_filesystems() first.")
    return _output_fs


def init_filesystems(resume_fs_url: str, jd_fs_url: str, output_fs_url: str = None) -> None:
    """
    Initialize the global filesystem instances.
    
    Args:
        resume_fs_url: URL for resume data storage
        jd_fs_url: URL for job description file storage
        output_fs_url: URL for output file storage (defaults to resume_fs_url/output)
    """
    global _resume_fs, _jd_fs, _output_fs
    _resume_fs = create_filesystem(resume_fs_url)
    _jd_fs = create_filesystem(jd_fs_url)
    
    # If no output_fs_url provided, create output subdirectory in resume filesystem
    if output_fs_url is None:
        if resume_fs_url.startswith("mem://"):
            output_fs_url = "mem://"
        else:
            output_fs_url = _join_fs_url(resume_fs_url, "output")
    
    _output_fs = create_filesystem(output_fs_url)


def is_initialized() -> bool:
    """Check if filesystems have been initialized."""
    return _resume_fs is not None and _jd_fs is not None and _output_fs is not None


def reset_filesystems() -> None:
    """Reset filesystem instances (mainly for testing)."""
    global _resume_fs, _jd_fs, _output_fs
    if _resume_fs is not None:
        _resume_fs.close()
    if _jd_fs is not None:
        _jd_fs.close()
    if _output_fs is not None:
        _output_fs.close()
    _resume_fs = None
    _jd_fs = None
    _output_fs = None