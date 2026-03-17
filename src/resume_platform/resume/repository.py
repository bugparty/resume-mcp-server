from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple

import rapidfuzz
import yaml
from fs.errors import FSError

from resume_platform.infrastructure.filesystem import get_resume_fs

logger = logging.getLogger(__name__)

SUMMARY_MAX_BULLETS = 3
SUMMARY_MAX_SKILLS = 12
SUMMARY_MAX_ENTRIES = 6


def _resume_filename(version: str) -> str:
    """Get the filename for a resume version."""
    return f"{version}.yaml"


def _load_temploate_resume() -> Dict[str, Any]:
    yaml_template_path = (
        Path(__file__).resolve().parents[3] / "templates" / "resume_template.yaml"
    )
    if not os.path.exists(yaml_template_path):
        raise FileNotFoundError("resume yaml template not found")
    with open(yaml_template_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            if data is None:
                raise ValueError(
                    f"Resume template file {yaml_template_path} is empty or contains only null values"
                )
            if isinstance(data, list):
                raise ValueError(
                    f"Resume template file {yaml_template_path} contains a list at root level, expected a dictionary"
                )
            raise ValueError(
                f"Resume template file {yaml_template_path} contains {type(data).__name__} at root level, expected a dictionary"
            )
        return data


def _load_resume(version: str) -> Dict[str, Any]:
    filename = _resume_filename(version)
    resume_fs = get_resume_fs()
    if not resume_fs.exists(filename):
        raise FileNotFoundError(f"Resume version not found: {version}")
    with resume_fs.open(filename, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

        # Ensure we always return a dictionary
        if not isinstance(data, dict):
            if data is None:
                raise ValueError(
                    f"Resume file {filename} is empty or contains only null values"
                )
            elif isinstance(data, list):
                raise ValueError(
                    f"Resume file {filename} contains a list at root level, expected a dictionary"
                )
            else:
                raise ValueError(
                    f"Resume file {filename} contains {type(data).__name__} at root level, expected a dictionary"
                )

        return data


def _save_resume(version: str, data: Dict[str, Any]) -> None:
    filename = _resume_filename(version)
    resume_fs = get_resume_fs()
    with resume_fs.open(filename, "w", encoding="utf-8") as handle:
        yaml.dump(data, handle, allow_unicode=True, sort_keys=False)


def find_resume_versions() -> List[str]:
    resume_fs = get_resume_fs()
    try:
        # Get all yaml files and extract their stems (names without extension)
        yaml_files = [name for name in resume_fs.listdir(".") if name.endswith(".yaml")]
        return sorted(name[:-5] for name in yaml_files)  # Remove .yaml extension
    except FSError as e:
        logger.warning("Could not list resume versions: %s", e)
        return []


def _dedupe_preserve_order(items: List[str], limit: int | None = None) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if not item:
            continue
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if limit is not None and len(result) >= limit:
            break
    return result


def _get_section(
    version: str, section_id: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    data = _load_resume(version)
    for section in data.get("sections", []):
        if section.get("id") == section_id:
            return data, section
    sections = data.get("sections", [])
    sections = [str(section.get("id")) for section in sections if section.get("id") is not None]
    all_available_section_ids = ", ".join(sections)
    closer_sections = rapidfuzz.process.extract(section_id, sections, limit=1)

    if closer_sections:
        closer_section_ids = [section[0] for section in closer_sections]
        error_message = f"Section '{section_id}' not found, did you mean '{closer_section_ids[0]}'?, all available section ids are: {all_available_section_ids}"
    else:
        error_message = f"Section '{section_id}' not found, no close match found. Available section ids are: {all_available_section_ids}"
    raise KeyError(error_message)


def set_section_visibility(version: str, section_id: str, enabled: bool) -> Dict[str, Any]:
    """Update style.section_disabled for a given section id.

    Returns a dict with updated style block for callers to format.
    """

    data = _load_resume(version)
    sections = data.get("sections") or []
    if not any(isinstance(s, dict) and s.get("id") == section_id for s in sections):
        raise KeyError(f"Section '{section_id}' not found in version '{version}'")

    style = data.get("style") or {}
    if not isinstance(style, dict):
        style = {}

    disabled = style.get("section_disabled") if isinstance(style.get("section_disabled"), dict) else {}
    if enabled:
        disabled.pop(section_id, None)
    else:
        disabled[section_id] = True

    if disabled:
        style["section_disabled"] = disabled
    elif "section_disabled" in style:
        style.pop("section_disabled", None)

    data["style"] = style
    _save_resume(version, data)
    return {"style": style}


def set_section_order(version: str, order: List[str]) -> Dict[str, Any]:
    """Replace style.section_order with the provided list (filtered to known ids)."""

    data = _load_resume(version)
    sections = [s for s in data.get("sections") or [] if isinstance(s, dict)]
    known_ids = [s.get("id") for s in sections if isinstance(s.get("id"), str)]
    known_set = set(known_ids)

    filtered_order = [sid for sid in order if isinstance(sid, str) and sid in known_set]

    style = data.get("style") or {}
    if not isinstance(style, dict):
        style = {}

    if filtered_order:
        style["section_order"] = filtered_order
    elif isinstance(style, dict):
        style.pop("section_order", None)

    data["style"] = style
    _save_resume(version, data)
    return {"style": style, "skipped_ids": [sid for sid in order if sid not in known_set]}


def get_section_style(version: str) -> Dict[str, Any]:
    """Return the current style settings (order/disabled) for a resume version."""

    data = _load_resume(version)
    style = data.get("style") if isinstance(data.get("style"), dict) else {}

    order = style.get("section_order") if isinstance(style.get("section_order"), list) else []
    disabled = (
        style.get("section_disabled") if isinstance(style.get("section_disabled"), dict) else {}
    )

    return {"style": {"section_order": order, "section_disabled": disabled}}


def load_complete_resume_as_dict(version: str) -> Dict[str, Any]:
    return _load_resume(version)
