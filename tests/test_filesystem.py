from __future__ import annotations

import os
from uuid import uuid4

import pytest

from resume_platform.infrastructure import filesystem as fs_module
from resume_platform.infrastructure.settings import load_settings


class _DummyFS:
    def close(self) -> None:
        return None


@pytest.fixture
def preserve_global_filesystems():
    """Restore the module-level filesystem globals after a test mutates them.

    Several test modules call init_filesystems() at import time, so the globals
    are initialised once during collection and then shared by every test in the
    process. A test that leaves them reset makes every later test relying on
    that import-time initialisation fail with "filesystem not initialized".
    """
    saved = (fs_module._resume_fs, fs_module._jd_fs, fs_module._output_fs)
    try:
        yield
    finally:
        fs_module._resume_fs, fs_module._jd_fs, fs_module._output_fs = saved


def test_join_fs_url_for_s3() -> None:
    assert fs_module._join_fs_url("s3://bucket/path", "output") == "s3://bucket/path/output"
    assert fs_module._join_fs_url("s3://bucket/path/", "/output/") == "s3://bucket/path/output"


def test_join_fs_url_for_local_path() -> None:
    joined = fs_module._join_fs_url("/tmp/resumes", "output")
    assert joined.endswith("/tmp/resumes/output")


def test_create_filesystem_s3_without_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fs_s3fs":
            raise ImportError("missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="fs-s3fs"):
        fs_module.create_filesystem("s3://example-bucket/resumes")


def test_init_filesystems_uses_s3_output_subpath(
    monkeypatch: pytest.MonkeyPatch, preserve_global_filesystems: None
) -> None:
    created_urls: list[str] = []

    def fake_create_filesystem(url: str):
        created_urls.append(url)
        return _DummyFS()

    monkeypatch.setattr(fs_module, "create_filesystem", fake_create_filesystem)

    fs_module.init_filesystems("s3://resume-bucket/resumes", "s3://jd-bucket/jd")

    assert created_urls == [
        "s3://resume-bucket/resumes",
        "s3://jd-bucket/jd",
        "s3://resume-bucket/resumes/output",
    ]

    fs_module.reset_filesystems()


def test_load_settings_accepts_resume_fs_ur_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No cleanup fixture needed: load_settings() is a pure builder, so asserting
    # on env parsing here cannot repoint the process settings.
    monkeypatch.delenv("RESUME_FS_URL", raising=False)
    monkeypatch.setenv("RESUME_FS_UR", "s3://resume-bucket/resumes")

    settings = load_settings()

    assert settings.resume_fs_url == "s3://resume-bucket/resumes"


def test_s3_resume_fs_read_write_smoke_from_env() -> None:
    s3_url = os.getenv("RESUME_FS_URL") or os.getenv("RESUME_FS_UR")
    if not s3_url or not s3_url.startswith("s3://"):
        pytest.skip("RESUME_FS_URL/RESUME_FS_UR is not configured with s3://")

    fs = fs_module.create_filesystem(s3_url)
    file_name = f"copilot_s3_smoke_{uuid4().hex}.txt"
    payload = "copilot s3 read write smoke"

    try:
        fs.writetext(file_name, payload)
        assert fs.readtext(file_name) == payload
        assert fs.exists(file_name)
        fs.remove(file_name)
    finally:
        fs.close()
