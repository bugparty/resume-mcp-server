"""Editing resume content through its Markdown text view.

Edits are addressed by ``(version_name, section_id)``; ``section_id=None``
targets the whole-resume text view. Every edit parses the Markdown back into
the structured YAML, validates the result, and only then saves, so a bad edit
never corrupts the stored document.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Literal

from resume_platform.resume_input_parser import (
    SECTION_PARSERS,
    parse_header_markdown,
    parse_raw_markdown,
)

from .repository import find_section, load_resume, save_resume
from .views import (
    FORMAT_INSTRUCTION_COMMENT,
    HEADER_SECTION_ID,
    MIN_FORMATTED_CONTENT_BYTES,
    format_hint,
    render_section_body,
    render_text_body,
    strip_instruction_comment,
)

InsertPosition = Literal["start", "end", "before", "after"]
INSERT_POSITIONS = {"start", "end", "before", "after"}


def _target(version_name: str, section_id: str | None) -> str:
    return version_name if section_id is None else f"{version_name}/{section_id}"


def _non_empty_line_count(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.strip())


def _extract_heading_title(markdown: str) -> str | None:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("##") and not line.startswith("###"):
            return line.lstrip("#").strip().lower()
    return None


def _looks_like_multi_section_resume(markdown: str) -> bool:
    headings = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip().startswith("##") and not line.strip().startswith("###")
    ]
    return len(headings) > 1


def _has_entry_markers(markdown: str) -> bool:
    return any(marker in markdown for marker in ("###", "**")) or bool(
        re.search(r"^\s*[-*]\s+", markdown, re.MULTILINE)
    )


def _build_format_error(
    target: str,
    section_id: str,
    section_type: str,
    reason: str,
    *,
    details: str | None = None,
) -> str:
    lines = [
        f"Failed to parse updated content for '{target}'.",
        f"{reason} The update was not saved.",
    ]
    if details:
        lines.append(details)
    lines.append(
        "Tip: call `read_resume_text` first and preserve the same heading and bullet structure."
    )
    lines.append(format_hint(section_id, section_type))
    return "\n".join(lines)


def _validate_common_markdown(
    target: str, section_id: str, section_type: str, markdown: str
) -> str | None:
    if FORMAT_INSTRUCTION_COMMENT in markdown:
        return _build_format_error(
            target,
            section_id,
            section_type,
            "The input still contains the loader instruction comment.",
            details="Submit only the section markdown itself, not the HTML comment wrapper.",
        )
    if _looks_like_multi_section_resume(markdown):
        return _build_format_error(
            target,
            section_id,
            section_type,
            "This tool can update only one section at a time.",
            details="The input appears to contain multiple '##' section headings.",
        )
    heading_title = _extract_heading_title(markdown)
    if heading_title and section_id.replace("_", " ").lower() not in heading_title:
        return _build_format_error(
            target,
            section_id,
            section_type,
            "The section title/type may not match the target section.",
            details=f"Expected a heading for '{section_id}', but received '## {heading_title.title()}'.",
        )
    return None


def _validate_parsed_section(
    target: str,
    markdown: str,
    section_before: Dict[str, Any],
    section_after: Dict[str, Any],
    section_id: str,
    section_type: str,
) -> str | None:
    common_error = _validate_common_markdown(target, section_id, section_type, markdown)
    if common_error:
        return common_error

    content_is_substantial = len(markdown.encode("utf-8")) > MIN_FORMATTED_CONTENT_BYTES
    line_count = _non_empty_line_count(markdown)

    if section_type in {"experience", "projects", "education"}:
        entries = section_after.get("entries") or []
        if content_is_substantial and not entries:
            details = "Possible issue: the entry heading format does not match the expected markdown structure."
            if _has_entry_markers(markdown) or line_count >= 2:
                details += " Expected supported entry headings such as '### Role — Company | Period' or the section-specific alternative below."
            return _build_format_error(
                target,
                section_id,
                section_type,
                "The parsed section became empty.",
                details=details,
            )
    elif section_type == "skills":
        groups = section_after.get("groups") or []
        has_valid_category = any(
            (group.get("category") or "").strip() for group in groups
        )
        has_items = any(group.get("items") for group in groups)
        if content_is_substantial and (
            not groups or not has_valid_category or (line_count >= 2 and not has_items)
        ):
            return _build_format_error(
                target,
                section_id,
                section_type,
                "The skills content could not be parsed into valid categories/items.",
                details="Possible issue: each line should follow a category format such as '- Programming: Python, Go'.",
            )
    elif section_type == "summary":
        bullets = section_after.get("bullets") or []
        if content_is_substantial and not bullets:
            return _build_format_error(
                target,
                section_id,
                section_type,
                "The summary content became empty after parsing.",
                details="Possible issue: the section is missing bullet lines or concise summary text.",
            )
    elif section_type == "raw":
        if content_is_substantial and not (section_after.get("content") or "").strip():
            return _build_format_error(
                target,
                section_id,
                section_type,
                "The custom section content became empty after parsing.",
            )
    return None


def _parse_into_section(
    version_name: str, section_id: str, section: Dict[str, Any], markdown: str
) -> None:
    parser = SECTION_PARSERS.get(section_id) or SECTION_PARSERS.get(
        section.get("type", "raw"), parse_raw_markdown
    )
    parser(markdown, section, version_name, section_id)


def _apply_header(
    data: Dict[str, Any], target: str, markdown: str, *, allow_empty: bool
) -> Dict[str, Any]:
    error = _validate_common_markdown(
        target, HEADER_SECTION_ID, HEADER_SECTION_ID, markdown
    )
    if error:
        raise ValueError(error)
    updates = parse_header_markdown(markdown)
    if not updates:
        if allow_empty and _non_empty_line_count(markdown) <= 1:
            return {}
        raise ValueError(
            _build_format_error(
                target,
                HEADER_SECTION_ID,
                HEADER_SECTION_ID,
                "Header content must contain at least one 'key: value' pair.",
                details="Example: 'email: john.doe@example.com'",
            )
        )
    data.setdefault("metadata", {}).update(updates)
    return updates


def _apply_section(
    data: Dict[str, Any], version_name: str, section_id: str, markdown: str
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse ``markdown`` into the section in ``data`` (in place) and validate.

    Returns ``(section_before, section_after)``.
    """
    target = _target(version_name, section_id)
    section = find_section(data, section_id, version_name=version_name)
    before = copy.deepcopy(section)
    section_type = section.get("type", "raw")
    _parse_into_section(version_name, section_id, section, markdown)
    error = _validate_parsed_section(
        target, markdown, before, section, section_id, section_type
    )
    if error:
        raise ValueError(error)
    return before, section


def update_section(version_name: str, section_id: str, new_content: str) -> str:
    """Replace one section (or the header) with new Markdown content."""
    markdown = (new_content or "").strip()
    target = _target(version_name, section_id)
    data = load_resume(version_name)

    if section_id == HEADER_SECTION_ID:
        updates = _apply_header(data, target, markdown, allow_empty=False)
        save_resume(version_name, data)
        return f"Updated {target}. updated metadata: {updates}"

    before, after = _apply_section(data, version_name, section_id, markdown)
    save_resume(version_name, data)
    result = f"Updated {target}. updated section: {after}"
    if before == after:
        result += " No effective content change detected."
    return result


def _split_top_level_blocks(markdown: str) -> List[str]:
    blocks: List[str] = []
    current: List[str] = []
    for line in markdown.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("##") and not stripped.startswith("###") and current:
            blocks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _write_whole_resume(version_name: str, markdown: str) -> str:
    data = load_resume(version_name)
    blocks = _split_top_level_blocks(markdown)
    expected_ids = [HEADER_SECTION_ID] + [
        section["id"]
        for section in data.get("sections") or []
        if isinstance(section, dict) and isinstance(section.get("id"), str)
    ]
    if len(blocks) != len(expected_ids):
        raise ValueError(
            f"Failed to update '{version_name}': whole-resume editing cannot add, "
            "remove, or reorder top-level '##' blocks."
        )

    working = copy.deepcopy(data)
    for section_id, block in zip(expected_ids, blocks):
        if section_id == HEADER_SECTION_ID:
            _apply_header(
                working, _target(version_name, section_id), block, allow_empty=True
            )
        else:
            _apply_section(working, version_name, section_id, block)

    save_resume(version_name, working)
    return f"Updated {version_name} via editable text view."


def _current_text(version_name: str, section_id: str | None) -> str:
    if section_id is None:
        return render_text_body(load_resume(version_name))
    return render_section_body(version_name, section_id)


def _write_text(version_name: str, section_id: str | None, markdown: str) -> str:
    normalized = strip_instruction_comment(markdown)
    if section_id is None:
        return _write_whole_resume(version_name, normalized)
    return update_section(version_name, section_id, normalized)


def _require_single_match(
    text: str, needle: str, *, action: str, target: str, needle_name: str
) -> None:
    count = text.count(needle) if needle else 0
    if count == 1:
        return
    if count == 0:
        raise ValueError(
            f"Could not {action} in '{target}': {needle_name} was not found. "
            "Call `read_resume_text` first and use a more exact snippet."
        )
    preview = needle[:80].replace("\n", "\\n")
    raise ValueError(
        f"Could not {action} in '{target}': {needle_name} matched {count} times. "
        f"Use a more specific snippet or anchor. Preview: '{preview}'"
    )


def replace_text(
    version_name: str, old_text: str, new_text: str, section_id: str | None = None
) -> str:
    """Replace exactly one occurrence of ``old_text`` in the text view."""
    current = _current_text(version_name, section_id)
    _require_single_match(
        current,
        old_text,
        action="replace text",
        target=_target(version_name, section_id),
        needle_name="old_text",
    )
    return _write_text(version_name, section_id, current.replace(old_text, new_text, 1))


def insert_text(
    version_name: str,
    new_text: str,
    position: InsertPosition | str,
    anchor_text: str | None = None,
    section_id: str | None = None,
) -> str:
    """Insert ``new_text`` at the start/end, or before/after a unique anchor."""
    target = _target(version_name, section_id)
    if position not in INSERT_POSITIONS:
        allowed = ", ".join(sorted(INSERT_POSITIONS))
        raise ValueError(
            f"Invalid insert position '{position}'. Expected one of: {allowed}."
        )
    current = _current_text(version_name, section_id)

    if position == "start":
        updated = new_text + current
    elif position == "end":
        updated = current + new_text
    else:
        if not anchor_text:
            raise ValueError(
                f"Insert position '{position}' requires `anchor_text` in '{target}'."
            )
        _require_single_match(
            current,
            anchor_text,
            action="insert text",
            target=target,
            needle_name="anchor_text",
        )
        replacement = (
            new_text + anchor_text if position == "before" else anchor_text + new_text
        )
        updated = current.replace(anchor_text, replacement, 1)
    return _write_text(version_name, section_id, updated)


def delete_text(version_name: str, old_text: str, section_id: str | None = None) -> str:
    """Delete exactly one occurrence of ``old_text`` from the text view."""
    current = _current_text(version_name, section_id)
    _require_single_match(
        current,
        old_text,
        action="delete text",
        target=_target(version_name, section_id),
        needle_name="old_text",
    )
    return _write_text(version_name, section_id, current.replace(old_text, "", 1))
