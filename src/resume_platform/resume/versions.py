"""Creating, copying and deleting resume versions."""

from __future__ import annotations

from .repository import (
    BASE_VERSION,
    delete_resume,
    load_resume,
    load_template,
    save_resume,
    validate_version_name,
    version_exists,
)


def _require_absent(version_name: str) -> None:
    if version_exists(version_name):
        raise ValueError(
            f"Resume version '{version_name}' already exists. "
            "Delete it first or choose a different name."
        )


def create_version(version_name: str) -> str:
    """Create a new version from the standard template."""
    version_name = validate_version_name(version_name)
    _require_absent(version_name)
    save_resume(version_name, load_template())
    return f"Created resume version '{version_name}' from the standard template."


def copy_version(source_version: str, target_version: str) -> str:
    source_version = validate_version_name(source_version)
    target_version = validate_version_name(target_version)
    if source_version == target_version:
        raise ValueError("Source and target version names must be different.")
    data = load_resume(source_version)
    _require_absent(target_version)
    save_resume(target_version, data)
    return f"Copied '{source_version}' to '{target_version}'."


def delete_version(version_name: str) -> str:
    version_name = validate_version_name(version_name)
    if version_name == BASE_VERSION:
        raise ValueError(
            f"Cannot delete the base resume version '{BASE_VERSION}'; "
            "it is the main template."
        )
    delete_resume(version_name)
    return f"Resume version '{version_name}' deleted."
