from __future__ import annotations

import pytest

from resume_platform.infrastructure import filesystem as fs_module


class _DummyFS:
    def close(self) -> None:
        return None


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


def test_init_filesystems_uses_s3_output_subpath(monkeypatch: pytest.MonkeyPatch) -> None:
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
