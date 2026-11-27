"""S3 connection settings from the environment, shared by the S3 filesystem
and the upload client.

Each setting accepts a project-specific name first, then generic aliases, so
the same deployment config works for Cloudflare R2, MinIO or AWS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_ALIASES = {
    "endpoint_url": ("RESUME_S3_ENDPOINT_URL", "S3_ENDPOINT_URL"),
    "region": ("RESUME_S3_REGION", "AWS_REGION"),
    "access_key_id": (
        "RESUME_S3_ACCESS_KEY_ID",
        "RESUME_S3_ACCESS_KEY",
        "S3_ACCESS_KEY_ID",
        "AWS_ACCESS_KEY_ID",
    ),
    "secret_access_key": (
        "RESUME_S3_SECRET_ACCESS_KEY",
        "RESUME_S3_SECRET_KEY",
        "S3_SECRET_ACCESS_KEY",
        "AWS_SECRET_ACCESS_KEY",
    ),
}


def _first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@dataclass(frozen=True)
class S3Connection:
    endpoint_url: str | None
    region: str | None
    access_key_id: str | None
    secret_access_key: str | None

    @classmethod
    def from_env(cls) -> S3Connection:
        return cls(**{field: _first_env(names) for field, names in _ALIASES.items()})
