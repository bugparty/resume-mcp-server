"""
Filesystem abstraction layer using PyFilesystem2.

This module provides a unified interface for file operations, supporting
local filesystem and future S3 integration through configuration.
"""

from __future__ import annotations

from typing import Optional
from fs.base import FS
from fs.osfs import OSFS
from fs.memoryfs import MemoryFS


def create_filesystem(fs_url: str) -> FS:
    """
    Create a filesystem instance based on the provided URL.
    
    Args:
        fs_url: Filesystem URL. Supported formats:
               - Local path: "/path/to/directory"
               - Memory filesystem: "mem://" (for testing)
               - S3 (future): "s3://bucket/path"
    
    Returns:
        FS: A PyFilesystem2 filesystem instance
        
    Raises:
        NotImplementedError: For unsupported filesystem types
        ValueError: For invalid URLs
    """
    if not fs_url:
        raise ValueError("Filesystem URL cannot be empty")
        
    if fs_url.startswith("s3://"):
        # Future S3 implementation
        # from fs.s3fs import S3FS
        # return S3FS.from_url(fs_url)
        raise NotImplementedError("S3 filesystem not implemented yet")
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
        from pathlib import Path
        if resume_fs_url.startswith("mem://"):
            output_fs_url = "mem://"
        else:
            output_fs_url = str(Path(resume_fs_url) / "output")
    
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