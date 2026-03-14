from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, ClassVar
import warnings


class SettingsError(Exception):
    """Settings related exceptions."""
    pass


@dataclass
class AppSettings:
    data_dir: Path
    summary_path: Path
    jd_dir: Path
    logs_dir: Path
    # Filesystem URLs for PyFilesystem2
    resume_fs_url: str
    jd_fs_url: str

    # Class-level reference to singleton instance
    _instance: ClassVar[Optional["AppSettings"]] = None
    _initialized: ClassVar[bool] = False

    @property
    def aggregate_path(self) -> Path:  # pragma: no cover - compatibility shim
        warnings.warn(
            "AppSettings.aggregate_path is deprecated; use summary_path instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.summary_path

    @classmethod
    def get_instance(cls) -> Optional["AppSettings"]:
        """Return the singleton instance, or None if not initialized."""
        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if settings have been initialized."""
        return cls._instance is not None and cls._initialized


def _is_directory_writable(path: Path) -> bool:
    """Check if a directory can be created and written to."""

    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        with test_file.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        test_file.unlink()
        return True
    except Exception:
        return False


def load_settings(
    *,
    data_dir: str | Path | None = None,
    summary_path: str | Path | None = None,
    aggregate_path: str | Path | None = None,
    jd_dir: str | Path | None = None,
    resume_fs_url: str | None = None,
    jd_fs_url: str | None = None,
    force_reload: bool = False,
) -> AppSettings:
    """Load application settings with optional overrides.

    Args:
        data_dir: Override data directory path
        summary_path: Override summary file path
        aggregate_path: Deprecated, use summary_path
        jd_dir: Override job descriptions directory path
        resume_fs_url: Override resume filesystem URL
        jd_fs_url: Override JD filesystem URL
        force_reload: If True, ignore existing singleton and reload

    Returns:
        AppSettings instance (singleton)
    """
    # Return existing instance if already initialized (unless force_reload)
    if AppSettings._instance is not None and not force_reload:
        return AppSettings._instance

    root_dir = Path(__file__).resolve().parents[2]
    fallback_base = Path(os.getenv("TMPDIR", "/tmp")) / "resume_mcp"

    default_data_dir = root_dir / "data" / "resumes"
    default_summary = root_dir / "src" / "myagent" / "resume_summary.yaml"
    default_jd_dir = root_dir / "data" / "jd"
    default_logs_dir = root_dir / "logs"

    defaults_use_fallback = False
    if not _is_directory_writable(default_data_dir):
        defaults_use_fallback = True
    if not defaults_use_fallback and not _is_directory_writable(default_logs_dir):
        defaults_use_fallback = True

    if defaults_use_fallback:
        fallback_data_dir = fallback_base / "data" / "resumes"
        fallback_jd_dir = fallback_base / "data" / "jd"
        fallback_summary = fallback_base / "resume_summary.yaml"
        fallback_logs_dir = fallback_base / "logs"

        default_data_dir = fallback_data_dir
        default_jd_dir = fallback_jd_dir
        default_summary = fallback_summary
        default_logs_dir = fallback_logs_dir

    resolved_data_dir = Path(data_dir or os.getenv("RESUME_DATA_DIR", default_data_dir))
    resolved_summary = Path(
        summary_path
        or os.getenv("RESUME_SUMMARY_PATH")
        or aggregate_path
        or os.getenv("RESUME_AGGREGATE_PATH")
        or default_summary
    )
    resolved_jd_dir = Path(jd_dir or os.getenv("RESUME_JD_DIR", default_jd_dir))
    resolved_logs_dir = Path(os.getenv("LOGS_DIR", default_logs_dir))

    # Filesystem URLs - default to local filesystem using resolved paths
    resolved_resume_fs = resume_fs_url or os.getenv("RESUME_FS_URL", str(resolved_data_dir))
    resolved_jd_fs = jd_fs_url or os.getenv("JD_FS_URL", str(resolved_jd_dir))

    resolved_logs_dir.mkdir(parents=True, exist_ok=True)
    AppSettings._instance = AppSettings(
        data_dir=resolved_data_dir,
        summary_path=resolved_summary,
        jd_dir=resolved_jd_dir,
        logs_dir=resolved_logs_dir,
        resume_fs_url=resolved_resume_fs,
        jd_fs_url=resolved_jd_fs,
    )
    AppSettings._initialized = True
    return AppSettings._instance


def get_settings() -> AppSettings:
    """Return the cached settings, loading defaults if necessary."""

    if AppSettings._instance is None:
        return load_settings()
    return AppSettings._instance


def reset_settings() -> None:
    """Reset the singleton instance (mainly for testing)."""
    AppSettings._instance = None
    AppSettings._initialized = False
