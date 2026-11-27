"""S3 settings resolution shared by the S3 filesystem and the upload client."""

from __future__ import annotations

import pytest

from resume_platform.infrastructure import filesystem
from resume_platform.infrastructure.s3_config import _ALIASES, S3Connection

ALL_VARS = [name for names in _ALIASES.values() for name in names]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ALL_VARS:
        monkeypatch.delenv(name, raising=False)


def test_project_names_win_over_generic_aliases(monkeypatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "aws")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "generic")
    monkeypatch.setenv("RESUME_S3_ACCESS_KEY", "short")
    assert S3Connection.from_env().access_key_id == "short"
    monkeypatch.setenv("RESUME_S3_ACCESS_KEY_ID", "project")
    assert S3Connection.from_env().access_key_id == "project"


def test_empty_values_fall_through_to_the_next_alias(monkeypatch) -> None:
    monkeypatch.setenv("RESUME_S3_REGION", "")
    monkeypatch.setenv("AWS_REGION", "auto")
    assert S3Connection.from_env().region == "auto"


def test_filesystem_opener_kwargs_skip_unset_values(monkeypatch) -> None:
    assert filesystem._s3_open_kwargs() == {}
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://r2.example.com")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert filesystem._s3_open_kwargs() == {
        "endpoint_url": "https://r2.example.com",
        "aws_secret_access_key": "secret",
    }
