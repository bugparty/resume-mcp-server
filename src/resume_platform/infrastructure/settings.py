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
    logs_dir: Path
    vector_db_dir: Path
    index_status_path: Path
    embedding_provider: str
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


def _resolve_path(value: str | Path | None, *, base_dir: Path) -> Path:
    """Resolve relative config paths against the repository root."""

    if value is None:
        raise ValueError("Path value cannot be None.")

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path


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
    vector_db_dir: str | Path | None = None,
    index_status_path: str | Path | None = None,
    embedding_provider: str | None = None,
    resume_fs_url: str | None = None,
    jd_fs_url: str | None = None,
) -> AppSettings:
    """Load application settings with optional overrides."""

    root_dir = Path(__file__).resolve().parents[3]
    fallback_base = Path(os.getenv("TMPDIR", "/tmp")) / "resume_mcp"

    default_data_dir = root_dir / "data" / "resumes"
    default_summary = root_dir / "src" / "resume_platform" / "resume_summary.yaml"
    default_jd_dir = root_dir / "data" / "jd"
    default_logs_dir = root_dir / "logs"
    default_vector_db_dir = root_dir / "data" / "vector_db"
    default_index_status_path = default_vector_db_dir / "index_status.json"

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

    resolved_data_dir = _resolve_path(
        data_dir or os.getenv("RESUME_DATA_DIR") or default_data_dir,
        base_dir=root_dir,
    )
    resolved_summary = _resolve_path(
        summary_path
        or os.getenv("RESUME_SUMMARY_PATH")
        or aggregate_path
        or os.getenv("RESUME_AGGREGATE_PATH")
        or default_summary,
        base_dir=root_dir,
    )
    resolved_jd_dir = _resolve_path(
        jd_dir or os.getenv("RESUME_JD_DIR") or default_jd_dir,
        base_dir=root_dir,
    )
    resolved_logs_dir = _resolve_path(
        os.getenv("LOGS_DIR") or default_logs_dir,
        base_dir=root_dir,
    )
    resolved_vector_db_dir = _resolve_path(
        vector_db_dir or os.getenv("VECTOR_DB_DIR") or default_vector_db_dir,
        base_dir=root_dir,
    )
    resolved_index_status_path = _resolve_path(
        index_status_path
        or os.getenv("VECTOR_INDEX_STATUS_PATH")
        or default_index_status_path,
        base_dir=root_dir,
    )
    resolved_embedding_provider = (
        embedding_provider
        or os.getenv("EMBEDDING_PROVIDER")
        or "google"
    ).lower()
    
    # Filesystem URLs - default to local filesystem using resolved paths
    resolved_resume_fs = (
        resume_fs_url
        or (str(resolved_data_dir) if data_dir is not None else None)
        or os.getenv("RESUME_FS_URL", str(resolved_data_dir))
    )
    resolved_jd_fs = (
        jd_fs_url
        or (str(resolved_jd_dir) if jd_dir is not None else None)
        or os.getenv("JD_FS_URL", str(resolved_jd_dir))
    )

    global _SETTINGS
    resolved_logs_dir.mkdir(parents=True, exist_ok=True)
    resolved_vector_db_dir.mkdir(parents=True, exist_ok=True)
    resolved_index_status_path.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS = AppSettings(
        data_dir=resolved_data_dir,
        summary_path=resolved_summary,
        jd_dir=resolved_jd_dir,
        logs_dir=resolved_logs_dir,
        vector_db_dir=resolved_vector_db_dir,
        index_status_path=resolved_index_status_path,
        embedding_provider=resolved_embedding_provider,
        resume_fs_url=resolved_resume_fs,
        jd_fs_url=resolved_jd_fs,
    )
    return _SETTINGS


def get_settings() -> AppSettings:
    """Return the cached settings, loading defaults if necessary."""

    if _SETTINGS is None:
        return load_settings()
    return _SETTINGS
