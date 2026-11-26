"""Application settings.

Importing this module has no side effects: ``settings`` is a lazy proxy that
resolves on first attribute access, mirroring ``django.conf.settings``. See
``docs/adr/0001-composition-root-and-runtime-lifecycle.md``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    data_dir: Path
    jd_dir: Path
    logs_dir: Path
    vector_db_dir: Path
    index_status_path: Path
    embedding_provider: str
    # Filesystem URLs for PyFilesystem2
    resume_fs_url: str
    jd_fs_url: str


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
    jd_dir: str | Path | None = None,
    vector_db_dir: str | Path | None = None,
    index_status_path: str | Path | None = None,
    embedding_provider: str | None = None,
    resume_fs_url: str | None = None,
    jd_fs_url: str | None = None,
) -> AppSettings:
    """Build an ``AppSettings`` from the environment plus optional overrides.

    Pure with respect to process state: it returns a new object and does *not*
    install it as the process settings — use :func:`bootstrap` or
    ``settings.configure()`` for that.

    This used to reassign a module-level ``_SETTINGS`` global, which meant any
    caller silently repointed the whole process. A test that merely asserted on
    env parsing left every later ``get_settings()`` reader pointed at its S3
    URL. See ADR-0001.
    """

    root_dir = Path(__file__).resolve().parents[3]
    fallback_base = Path(os.getenv("TMPDIR", "/tmp")) / "resume_mcp"

    default_data_dir = root_dir / "data" / "resumes"
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
        fallback_logs_dir = fallback_base / "logs"

        default_data_dir = fallback_data_dir
        default_jd_dir = fallback_jd_dir
        default_logs_dir = fallback_logs_dir

    resolved_data_dir = _resolve_path(
        data_dir or os.getenv("RESUME_DATA_DIR") or default_data_dir,
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
        embedding_provider or os.getenv("EMBEDDING_PROVIDER") or "google"
    ).lower()

    # Filesystem URLs - default to local filesystem using resolved paths
    # Keep RESUME_FS_UR as a backward-compatible alias for historical typoed envs.
    resolved_resume_fs = (
        resume_fs_url
        or (str(resolved_data_dir) if data_dir is not None else None)
        or os.getenv("RESUME_FS_URL")
        or os.getenv("RESUME_FS_UR")
        or str(resolved_data_dir)
    )
    resolved_jd_fs = (
        jd_fs_url
        or (str(resolved_jd_dir) if jd_dir is not None else None)
        or os.getenv("JD_FS_URL", str(resolved_jd_dir))
    )

    resolved_logs_dir.mkdir(parents=True, exist_ok=True)
    resolved_vector_db_dir.mkdir(parents=True, exist_ok=True)
    resolved_index_status_path.parent.mkdir(parents=True, exist_ok=True)
    return AppSettings(
        data_dir=resolved_data_dir,
        jd_dir=resolved_jd_dir,
        logs_dir=resolved_logs_dir,
        vector_db_dir=resolved_vector_db_dir,
        index_status_path=resolved_index_status_path,
        embedding_provider=resolved_embedding_provider,
        resume_fs_url=resolved_resume_fs,
        jd_fs_url=resolved_jd_fs,
    )


class LazySettings:
    """Hold the process settings, resolving them on first attribute access.

    Mirrors ``django.conf.settings``. Importing a module that does
    ``from ...settings import settings`` reads nothing and touches no
    filesystem; the first attribute access resolves and caches. That makes
    "import does not resolve settings" a structural property rather than a
    discipline every module has to remember — the thing #16 got wrong by
    snapshotting ``get_settings()`` at import.
    """

    def __init__(self) -> None:
        # Assigned here so __getattr__ (below) never sees them missing.
        self._wrapped: AppSettings | None = None
        self._overrides: dict[str, Any] = {}

    @property
    def is_resolved(self) -> bool:
        return self._wrapped is not None

    def configure(self, **overrides: Any) -> None:
        """Stage overrides for the first resolve. Must precede any access."""
        if self._wrapped is not None:
            raise RuntimeError(
                "settings are already resolved; configure() must precede first "
                "access. Use bootstrap(force=True) to rebuild from scratch."
            )
        self._overrides = overrides

    def reset(self) -> None:
        """Drop the resolved settings and any staged overrides."""
        self._wrapped = None
        self._overrides = {}

    def _resolve(self) -> AppSettings:
        if self._wrapped is None:
            self._wrapped = load_settings(**self._overrides)
        return self._wrapped

    def __getattr__(self, name: str) -> Any:
        # Only reached for names not found normally, i.e. not _wrapped or the
        # methods above — so this cannot recurse.
        return getattr(self._resolve(), name)


settings = LazySettings()  # import-time: zero side effects


def get_settings() -> AppSettings:
    """Return the process settings, resolving them on first use."""

    return settings._resolve()
