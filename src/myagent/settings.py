from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import warnings


@dataclass
class AppSettings:
    data_dir: Path
    summary_path: Path
    jd_dir: Path
    # Filesystem URLs for PyFilesystem2
    resume_fs_url: str
    jd_fs_url: str

    @property
    def aggregate_path(self) -> Path:  # pragma: no cover - compatibility shim
        warnings.warn(
            "AppSettings.aggregate_path is deprecated; use summary_path instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.summary_path


_SETTINGS: Optional[AppSettings] = None


def load_settings(
    *,
    data_dir: str | Path | None = None,
    summary_path: str | Path | None = None,
    aggregate_path: str | Path | None = None,
    jd_dir: str | Path | None = None,
    resume_fs_url: str | None = None,
    jd_fs_url: str | None = None,
) -> AppSettings:
    """Load application settings with optional overrides."""

    root_dir = Path(__file__).resolve().parents[2]
    default_data_dir = root_dir / "data" / "resumes"
    default_summary = root_dir / "src" / "myagent" / "resume_summary.yaml"
    default_jd_dir = root_dir / "data" / "jd"

    resolved_data_dir = Path(data_dir or os.getenv("RESUME_DATA_DIR", default_data_dir))
    resolved_summary = Path(
        summary_path
        or os.getenv("RESUME_SUMMARY_PATH")
        or aggregate_path
        or os.getenv("RESUME_AGGREGATE_PATH")
        or default_summary
    )
    resolved_jd_dir = Path(jd_dir or os.getenv("RESUME_JD_DIR", default_jd_dir))
    
    # Filesystem URLs - default to local filesystem using resolved paths
    resolved_resume_fs = resume_fs_url or os.getenv("RESUME_FS_URL", str(resolved_data_dir))
    resolved_jd_fs = jd_fs_url or os.getenv("JD_FS_URL", str(resolved_jd_dir))

    global _SETTINGS
    _SETTINGS = AppSettings(
        data_dir=resolved_data_dir,
        summary_path=resolved_summary,
        jd_dir=resolved_jd_dir,
        resume_fs_url=resolved_resume_fs,
        jd_fs_url=resolved_jd_fs,
    )
    return _SETTINGS


def get_settings() -> AppSettings:
    """Return the cached settings, loading defaults if necessary."""

    if _SETTINGS is None:
        return load_settings()
    return _SETTINGS
