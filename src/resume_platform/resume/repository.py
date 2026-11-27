"""Persistence for resume versions.

A *version* is one ``<version_name>.yaml`` document in the resume filesystem.
This module is the only place that knows about that file layout; everything
else works with version names and plain dicts.
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import Any

import rapidfuzz
import yaml
from fs.errors import FSError

from resume_platform.infrastructure.filesystem import get_resume_fs
from resume_platform.paths import RESUME_TEMPLATE_PATH

logger = logging.getLogger(__name__)

BASE_VERSION = "resume"
_VERSION_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")


class ResumeNotFoundError(FileNotFoundError):
    """The requested resume version does not exist."""


class SectionNotFoundError(KeyError):
    """The requested section id does not exist in a resume version."""

    def __str__(self) -> str:  # KeyError would repr() the message
        return str(self.args[0]) if self.args else ""


def validate_version_name(version_name: str) -> str:
    """Return the normalised version name or raise ``ValueError``.

    Names are file stems: no path separators, no ``.yaml`` suffix.
    """
    name = (version_name or "").strip()
    if not name:
        raise ValueError("Version name cannot be empty.")
    if name.endswith(".yaml"):
        raise ValueError(
            f"Version name '{name}' must not include the .yaml extension; "
            f"use '{name[:-5]}'."
        )
    if not _VERSION_NAME_RE.match(name):
        raise ValueError(
            f"Invalid version name '{name}'. Use letters, digits, '_', '-' or '.'."
        )
    return name


def _filename(version_name: str) -> str:
    return f"{validate_version_name(version_name)}.yaml"


def _parse_resume_document(text: str, source: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        kind = "empty" if data is None else type(data).__name__
        raise ValueError(f"{source} must contain a YAML mapping, got {kind}.")
    return data


def version_exists(version_name: str) -> bool:
    return get_resume_fs().exists(_filename(version_name))


def list_versions() -> list[str]:
    """Return the sorted names of all stored resume versions."""
    resume_fs = get_resume_fs()
    try:
        try:
            names = [n for n in resume_fs.listdir(".") if n.endswith(".yaml")]
        except FSError:
            names = []
        # Some S3 layouts expose objects only under nested prefixes.
        if not names:
            names = [
                PurePosixPath(path).name
                for path in resume_fs.walk.files(filter=["*.yaml"])
            ]
    except FSError as exc:
        logger.warning("Could not list resume versions: %s", exc)
        return []
    return sorted({name[: -len(".yaml")] for name in names if name.endswith(".yaml")})


def load_resume(version_name: str) -> dict[str, Any]:
    filename = _filename(version_name)
    resume_fs = get_resume_fs()
    if not resume_fs.exists(filename):
        raise ResumeNotFoundError(f"Resume version not found: {version_name}")
    return _parse_resume_document(
        resume_fs.readtext(filename, encoding="utf-8"), filename
    )


def save_resume(version_name: str, data: dict[str, Any]) -> None:
    text = yaml.dump(data, allow_unicode=True, sort_keys=False)
    get_resume_fs().writetext(_filename(version_name), text, encoding="utf-8")


def delete_resume(version_name: str) -> None:
    filename = _filename(version_name)
    resume_fs = get_resume_fs()
    if not resume_fs.exists(filename):
        raise ResumeNotFoundError(f"Resume version not found: {version_name}")
    resume_fs.remove(filename)


def load_template() -> dict[str, Any]:
    """The standard template new versions are created from."""
    if not RESUME_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Resume template not found: {RESUME_TEMPLATE_PATH}")
    return _parse_resume_document(
        RESUME_TEMPLATE_PATH.read_text(encoding="utf-8"), RESUME_TEMPLATE_PATH.name
    )


def section_ids(data: dict[str, Any]) -> list[str]:
    return [
        section["id"]
        for section in data.get("sections") or []
        if isinstance(section, dict) and isinstance(section.get("id"), str)
    ]


def find_section(
    data: dict[str, Any], section_id: str, *, version_name: str = ""
) -> dict[str, Any]:
    """Return the section dict (by reference) or raise with a suggestion."""
    for section in data.get("sections") or []:
        if isinstance(section, dict) and section.get("id") == section_id:
            return section

    available = section_ids(data)
    where = f" in version '{version_name}'" if version_name else ""
    message = f"Section '{section_id}' not found{where}."
    match = rapidfuzz.process.extractOne(section_id, available) if available else None
    if match:
        message += f" Did you mean '{match[0]}'?"
    message += f" Available section ids: header, {', '.join(available)}"
    raise SectionNotFoundError(message)


def get_section(
    version_name: str, section_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a version and return ``(document, section)``."""
    data = load_resume(version_name)
    return data, find_section(data, section_id, version_name=version_name)
