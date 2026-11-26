"""Shared pytest fixtures.

Every test runs against its own throwaway copy of ``tests/fixtures/test_data``
so tests can freely create, edit and delete resume versions without touching
the repository or leaking state into each other.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "test_data"


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """A private, writable copy of the fixture data tree for this test."""
    root = tmp_path / "_runtime" / "data"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


@pytest.fixture(autouse=True)
def runtime(data_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Bootstrap settings + filesystems against the per-test data copy."""
    from resume_platform.infrastructure.bootstrap import bootstrap

    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "_runtime" / "logs"))
    for var in ("RESUME_FS_URL", "RESUME_FS_UR", "JD_FS_URL"):
        monkeypatch.delenv(var, raising=False)

    settings = bootstrap(
        force=True,
        data_dir=data_root / "resumes",
        jd_dir=data_root / "jd",
        vector_db_dir=tmp_path / "_runtime" / "vector_db",
    )
    yield settings


@pytest.fixture
def reset_runtime_after(data_root: Path, tmp_path: Path):
    """Rebuild the per-test runtime after a test repoints the global filesystems."""
    from resume_platform.infrastructure.bootstrap import bootstrap

    try:
        yield
    finally:
        bootstrap(
            force=True,
            data_dir=data_root / "resumes",
            jd_dir=data_root / "jd",
            vector_db_dir=tmp_path / "_runtime" / "vector_db",
        )
