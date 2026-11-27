"""Section layout: which sections render, and in what order.

Stored per version under ``style.section_order`` / ``style.section_disabled``.
Shared by the Markdown view and the LaTeX renderer.
"""

from __future__ import annotations

from typing import Any

from .repository import find_section, load_resume, save_resume, section_ids


def _style(data: dict[str, Any]) -> dict[str, Any]:
    style = data.get("style")
    return style if isinstance(style, dict) else {}


def _layout_from_style(style: dict[str, Any]) -> dict[str, Any]:
    order = style.get("section_order")
    disabled = style.get("section_disabled")
    return {
        "section_order": list(order) if isinstance(order, list) else [],
        "section_disabled": dict(disabled) if isinstance(disabled, dict) else {},
    }


def apply_layout(
    sections: list[dict[str, Any]], style: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Return the sections to render, ordered and filtered by ``style``.

    Ids listed in ``section_order`` come first; remaining sections follow in
    document order. Sections flagged ``True`` in ``section_disabled`` are
    dropped.
    """
    sections = [s for s in sections or [] if isinstance(s, dict)]
    layout = _layout_from_style(style if isinstance(style, dict) else {})
    disabled = {sid for sid, flag in layout["section_disabled"].items() if flag is True}
    by_id = {s["id"]: s for s in sections if isinstance(s.get("id"), str)}

    ordered: list[dict[str, Any]] = []
    placed: set[str] = set()
    for section_id in layout["section_order"]:
        if section_id in by_id and section_id not in placed:
            placed.add(section_id)
            if section_id not in disabled:
                ordered.append(by_id[section_id])
    for section in sections:
        section_id = section.get("id")
        if section_id in placed or section_id in disabled:
            continue
        if isinstance(section_id, str):
            placed.add(section_id)
        ordered.append(section)
    return ordered


def get_layout(version_name: str) -> dict[str, Any]:
    """``{"section_order": [...], "section_disabled": {...}}`` for a version."""
    return _layout_from_style(_style(load_resume(version_name)))


def set_section_visibility(
    version_name: str, section_id: str, enabled: bool
) -> dict[str, Any]:
    """Show or hide one section; returns the updated layout."""
    data = load_resume(version_name)
    find_section(data, section_id, version_name=version_name)

    style = _style(data)
    disabled = _layout_from_style(style)["section_disabled"]
    if enabled:
        disabled.pop(section_id, None)
    else:
        disabled[section_id] = True

    if disabled:
        style["section_disabled"] = disabled
    else:
        style.pop("section_disabled", None)
    data["style"] = style
    save_resume(version_name, data)
    return _layout_from_style(style)


def set_section_order(version_name: str, order: list[str]) -> dict[str, Any]:
    """Set the preferred section order.

    Unknown ids are dropped and reported in ``skipped_ids``; sections not
    mentioned keep their document order after the listed ones.
    """
    data = load_resume(version_name)
    known = set(section_ids(data))
    kept = [sid for sid in order if sid in known]
    skipped = [sid for sid in order if sid not in known]

    style = _style(data)
    if kept:
        style["section_order"] = kept
    else:
        style.pop("section_order", None)
    data["style"] = style
    save_resume(version_name, data)
    return {**_layout_from_style(style), "skipped_ids": skipped}
