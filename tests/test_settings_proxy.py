"""Tests for the lazy settings proxy and the purity of load_settings().

See docs/adr/0001-composition-root-and-runtime-lifecycle.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from resume_platform.infrastructure.settings import (
    LazySettings,
    get_settings,
    load_settings,
)

SRC = Path(__file__).resolve().parents[1] / "src"


def test_load_settings_does_not_install_process_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_settings() builds an object; it must not repoint the process.

    This is the bug that made a test asserting on env parsing send every later
    get_settings() reader to S3 (see ADR-0001). It is now structurally
    impossible: the builder is pure, installing is bootstrap()'s job.
    """
    before = get_settings().resume_fs_url

    monkeypatch.setenv("RESUME_FS_URL", "s3://some-other-bucket/resumes")
    built = load_settings()

    assert built.resume_fs_url == "s3://some-other-bucket/resumes"
    assert get_settings().resume_fs_url == before


def test_importing_settings_module_resolves_nothing(tmp_path: Path) -> None:
    """Importing the module must not read env or touch the filesystem."""
    logs_dir = tmp_path / "logs"
    script = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        f"os.environ['LOGS_DIR'] = {str(logs_dir)!r}\n"
        "from resume_platform.infrastructure.settings import settings\n"
        # Resolving would create logs_dir as a side effect of load_settings().
        f"print(settings.is_resolved, not os.path.exists({str(logs_dir)!r}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False True", result.stderr


def test_proxy_resolves_on_first_attribute_access() -> None:
    proxy = LazySettings()
    assert proxy.is_resolved is False

    proxy.data_dir  # noqa: B018 - touching an attribute is the trigger

    assert proxy.is_resolved is True


def test_configure_overrides_are_applied_on_resolve(tmp_path: Path) -> None:
    proxy = LazySettings()
    proxy.configure(data_dir=tmp_path / "resumes", jd_dir=tmp_path / "jd")

    assert proxy.data_dir == tmp_path / "resumes"


def test_configure_after_resolve_raises(tmp_path: Path) -> None:
    """Reconfiguring settings someone may already have read is a bug, not a nudge."""
    proxy = LazySettings()
    proxy.data_dir  # noqa: B018 - resolve it

    with pytest.raises(RuntimeError, match="already resolved"):
        proxy.configure(data_dir=tmp_path / "late")


def test_reset_allows_reconfiguration(tmp_path: Path) -> None:
    proxy = LazySettings()
    proxy.data_dir  # noqa: B018 - resolve it

    proxy.reset()
    assert proxy.is_resolved is False

    proxy.configure(data_dir=tmp_path / "second", jd_dir=tmp_path / "jd")
    assert proxy.data_dir == tmp_path / "second"
