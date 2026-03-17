from __future__ import annotations

import copy
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Literal

import yaml
from langchain_core.messages import HumanMessage

from resume_platform.infrastructure.filesystem import get_resume_fs
from resume_platform.infrastructure.llm_config import get_llm
from resume_platform.infrastructure.settings import get_settings
from resume_platform.resume_input_parser import (
    SECTION_PARSERS,
    parse_header_markdown,
    parse_raw_markdown,
)

from .repository import (
    SUMMARY_MAX_BULLETS,
    SUMMARY_MAX_ENTRIES,
    SUMMARY_MAX_SKILLS,
    _dedupe_preserve_order,
    _load_resume,
    _resume_filename,
    _save_resume,
    find_resume_versions,
)
from .views import (
    FORMAT_INSTRUCTION_COMMENT,
    HEADER_SECTION_ID,
    HEADER_SECTION_TEMPLATE,
    MIN_FORMATTED_CONTENT_BYTES,
    SECTION_HINTS_BY_TYPE,
    _read_section_text_body,
    _render_resume_text_body,
    _render_section,
    _strip_instruction_comment,
    _target_to_version_and_section,
)


llm = None
INSERT_POSITIONS = {"start", "end", "before", "after"}


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


def _hint_for_section(section_id: str, section_type: str) -> str:
    if section_id == HEADER_SECTION_ID:
        return HEADER_SECTION_TEMPLATE
    return (
        SECTION_HINTS_BY_TYPE.get(section_id)
        or SECTION_HINTS_BY_TYPE.get(section_type)
        or SECTION_HINTS_BY_TYPE["raw"]
    )


def _build_format_error(
    module_path: str,
    section_id: str,
    section_type: str,
    reason: str,
    *,
    details: str | None = None,
) -> str:
    lines = [
        f"Failed to parse updated content for '{module_path}'.",
        f"{reason} The update was not saved.",
    ]
    if details:
        lines.append(details)
    lines.append("Tip: call `load_resume_section` first and preserve the same heading and bullet structure.")
    lines.append(_hint_for_section(section_id, section_type))
    return "\n".join(lines)


def _validate_common_markdown(
    module_path: str, section_id: str, section_type: str, markdown: str
) -> str | None:
    if FORMAT_INSTRUCTION_COMMENT in markdown:
        return _build_format_error(
            module_path,
            section_id,
            section_type,
            "The input still contains the loader instruction comment.",
            details="Submit only the section markdown itself, not the HTML comment wrapper.",
        )
    if _looks_like_multi_section_resume(markdown):
        return _build_format_error(
            module_path,
            section_id,
            section_type,
            "This tool can update only one section at a time.",
            details="The input appears to contain multiple '##' section headings.",
        )
    heading_title = _extract_heading_title(markdown)
    if heading_title and section_id.replace("_", " ").lower() not in heading_title:
        return _build_format_error(
            module_path,
            section_id,
            section_type,
            "The section title/type may not match the target section.",
            details=f"Expected a heading for '{section_id}', but received '## {heading_title.title()}'.",
        )
    return None


def _validate_parsed_section(
    module_path: str,
    markdown: str,
    section_before: Dict[str, Any],
    section_after: Dict[str, Any],
    section_id: str,
    section_type: str,
) -> str | None:
    common_error = _validate_common_markdown(module_path, section_id, section_type, markdown)
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
                module_path, section_id, section_type, "The parsed section became empty.", details=details
            )
    elif section_type == "skills":
        groups = section_after.get("groups") or []
        has_valid_category = any((group.get("category") or "").strip() for group in groups)
        has_items = any(group.get("items") for group in groups)
        if content_is_substantial and (not groups or not has_valid_category or (line_count >= 2 and not has_items)):
            return _build_format_error(
                module_path,
                section_id,
                section_type,
                "The skills content could not be parsed into valid categories/items.",
                details="Possible issue: each line should follow a category format such as '- Programming: Python, Go'.",
            )
    elif section_type == "summary":
        bullets = section_after.get("bullets") or []
        if content_is_substantial and not bullets:
            return _build_format_error(
                module_path,
                section_id,
                section_type,
                "The summary content became empty after parsing.",
                details="Possible issue: the section is missing bullet lines or concise summary text.",
            )
    elif section_type == "raw":
        if content_is_substantial and not (section_after.get("content") or "").strip():
            return _build_format_error(
                module_path,
                section_id,
                section_type,
                "The custom section content became empty after parsing.",
            )
    return None


def _update_section_from_markdown(
    version: str, section_id: str, section: Dict[str, Any], markdown: str
) -> None:
    parser = SECTION_PARSERS.get(section_id)
    if parser is None:
        parser = SECTION_PARSERS.get(section.get("type", "raw"), parse_raw_markdown)
    parser(markdown, section, version, section_id)


def _count_matches(text: str, needle: str) -> int:
    if not needle:
        return 0
    return text.count(needle)


def _replace_once(text: str, old_text: str, new_text: str) -> str:
    return text.replace(old_text, new_text, 1)


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


def _build_match_error(
    action: str,
    target_path: str,
    needle_name: str,
    needle: str,
    match_count: int,
) -> str:
    if match_count == 0:
        return (
            f"Could not {action} in '{target_path}': {needle_name} was not found. "
            "Call `read_resume_text` first and use a more exact snippet."
        )
    preview = needle[:80].replace("\n", "\\n")
    return (
        f"Could not {action} in '{target_path}': {needle_name} matched "
        f"{match_count} times. Use a more specific snippet or anchor. "
        f"Preview: '{preview}'"
    )


def _apply_section_markdown(
    data: Dict[str, Any],
    version: str,
    section_id: str,
    markdown: str,
    module_path: str,
) -> str | None:
    if section_id == HEADER_SECTION_ID:
        header_error = _validate_common_markdown(module_path, section_id, HEADER_SECTION_ID, markdown)
        if header_error:
            return header_error
        metadata_updates = parse_header_markdown(markdown)
        if not metadata_updates:
            if _non_empty_line_count(markdown) <= 1:
                return None
            return _build_format_error(
                module_path,
                section_id,
                HEADER_SECTION_ID,
                "Header content must contain at least one 'key: value' pair.",
                details="Example: 'email: john.doe@example.com'",
            )
        data.setdefault("metadata", {}).update(metadata_updates)
        return None

    sections = data.get("sections", [])
    section = next(
        (item for item in sections if isinstance(item, dict) and item.get("id") == section_id),
        None,
    )
    if section is None:
        raise KeyError(f"Section '{section_id}' not found in version '{version}'")

    section_before = copy.deepcopy(section)
    section_type = section.get("type", "raw")
    _update_section_from_markdown(version, section_id, section, markdown)
    return _validate_parsed_section(
        module_path, markdown, section_before, section, section_id, section_type
    )


def _write_resume_text_body(version: str, section_id: str | None, markdown: str) -> str:
    normalized = _strip_instruction_comment(markdown)
    if section_id is not None:
        return update_resume_section(f"{version}/{section_id}", normalized)

    data = _load_resume(version)
    edited_blocks = _split_top_level_blocks(normalized)
    expected_section_ids = [HEADER_SECTION_ID]
    expected_section_ids.extend(
        section.get("id")
        for section in data.get("sections", [])
        if isinstance(section, dict) and isinstance(section.get("id"), str)
    )
    if len(edited_blocks) != len(expected_section_ids):
        raise ValueError(
            f"Failed to update '{version}': whole-resume editing cannot add, "
            "remove, or reorder top-level '##' blocks."
        )

    working_copy = copy.deepcopy(data)
    for current_section_id, block in zip(expected_section_ids, edited_blocks):
        module_path = f"{version}/{current_section_id}" if current_section_id != HEADER_SECTION_ID else f"{version}/header"
        error = _apply_section_markdown(working_copy, version, current_section_id, block, module_path)
        if error:
            raise ValueError(error)

    _save_resume(version, working_copy)
    return f"Updated {version} via editable text view."


def update_resume_section(module_path: str, new_content: str | None = None) -> str:
    module_path = module_path.strip()
    if new_content is None and ":" in module_path:
        module_path, new_content = module_path.split(":", 1)
    if new_content is None:
        raise ValueError("Missing new content for section update.")
    new_content = new_content.strip()
    if "/" not in module_path:
        raise ValueError("Module path must follow 'version/section' format.")

    version, section_id = module_path.split("/", 1)
    if section_id == HEADER_SECTION_ID:
        header_error = _validate_common_markdown(module_path, section_id, HEADER_SECTION_ID, new_content)
        if header_error:
            raise ValueError(header_error)
        data = _load_resume(version)
        metadata_updates = parse_header_markdown(new_content)
        if not metadata_updates:
            raise ValueError(_build_format_error(
                module_path,
                section_id,
                HEADER_SECTION_ID,
                "Header content must contain at least one 'key: value' pair.",
                details="Example: 'email: john.doe@example.com'",
            ))
        data.setdefault("metadata", {}).update(metadata_updates)
        _save_resume(version, data)
        return f"Updated {module_path}. updated metadata: {metadata_updates}"

    data = _load_resume(version)
    section = next(
        (item for item in data.get("sections", []) if isinstance(item, dict) and item.get("id") == section_id),
        None,
    )
    if section is None:
        from .repository import _get_section

        _get_section(version, section_id)
    assert section is not None
    section_before = copy.deepcopy(section)
    section_type = section.get("type", "raw")
    _update_section_from_markdown(version, section_id, section, new_content)
    validation_error = _validate_parsed_section(
        module_path, new_content, section_before, section, section_id, section_type
    )
    if validation_error:
        raise ValueError(validation_error)
    _save_resume(version, data)
    result = f"Updated {module_path}. updated section: {section}"
    if section_before == section:
        result += " No effective content change detected."
    return result


def replace_resume_text(target_path: str, old_text: str, new_text: str) -> str:
    version, section_id = _target_to_version_and_section(target_path)
    current_text = _render_resume_text_body(version) if section_id is None else _read_section_text_body(version, section_id)
    match_count = _count_matches(current_text, old_text)
    if match_count != 1:
        raise ValueError(_build_match_error("replace text", target_path, "old_text", old_text, match_count))
    return _write_resume_text_body(version, section_id, _replace_once(current_text, old_text, new_text))


def insert_resume_text(
    target_path: str,
    new_text: str,
    position: Literal["start", "end", "before", "after"] | str,
    anchor_text: str | None = None,
) -> str:
    version, section_id = _target_to_version_and_section(target_path)
    current_text = _render_resume_text_body(version) if section_id is None else _read_section_text_body(version, section_id)
    if position not in INSERT_POSITIONS:
        allowed = ", ".join(sorted(INSERT_POSITIONS))
        raise ValueError(f"Invalid insert position '{position}'. Expected one of: {allowed}.")
    if position in {"before", "after"}:
        if not anchor_text:
            raise ValueError(f"Insert position '{position}' requires `anchor_text` in '{target_path}'.")
        match_count = _count_matches(current_text, anchor_text)
        if match_count != 1:
            raise ValueError(_build_match_error("insert text", target_path, "anchor_text", anchor_text, match_count))
        updated_text = (
            _replace_once(current_text, anchor_text, new_text + anchor_text)
            if position == "before"
            else _replace_once(current_text, anchor_text, anchor_text + new_text)
        )
    elif position == "start":
        updated_text = new_text + current_text
    else:
        updated_text = current_text + new_text
    return _write_resume_text_body(version, section_id, updated_text)


def delete_resume_text(target_path: str, old_text: str) -> str:
    version, section_id = _target_to_version_and_section(target_path)
    current_text = _render_resume_text_body(version) if section_id is None else _read_section_text_body(version, section_id)
    match_count = _count_matches(current_text, old_text)
    if match_count != 1:
        raise ValueError(_build_match_error("delete text", target_path, "old_text", old_text, match_count))
    return _write_resume_text_body(version, section_id, _replace_once(current_text, old_text, ""))


def update_main_resume(file_name: str, file_content: str) -> str:
    version = file_name.replace(".yaml", "")
    try:
        data = yaml.safe_load(file_content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML content: {exc}") from exc
    _save_resume(version, data)
    return f"Replaced resume definition for {version}."


def create_new_version(new_version_name: str) -> str:
    new_version_name = new_version_name.strip()
    if not new_version_name:
        raise ValueError("Version name cannot be empty.")
    target_filename = _resume_filename(new_version_name)
    resume_fs = get_resume_fs()
    if resume_fs.exists(target_filename):
        raise ValueError(f"Version '{new_version_name}' already exists.")
    template_path = Path(__file__).resolve().parents[3] / "templates" / "resume_template.yaml"
    if not template_path.exists():
        raise FileNotFoundError("Standard resume template not found at templates/resume_template.yaml.")
    with template_path.open("r", encoding="utf-8") as handle:
        base = yaml.safe_load(handle)
    _save_resume(new_version_name, base)
    return f"Created new resume version '{new_version_name}' from standard template."


def tailor_section_for_jd(module_path: str, section_content: str, jd_analysis: str) -> str:
    prompt = f"""
You are updating a resume section stored as Markdown. Preserve the existing heading structure and bullet formatting while tailoring the content to match the job description analysis.

Current Section Markdown:
---
{section_content}
---

Job Description Analysis:
---
{jd_analysis}
---

Return revised Markdown for the section. Use concise bullet points and keep any heading titles unchanged.
    """
    try:
        global llm
        if llm is None:
            llm = get_llm(provider="deepseek")
        response = llm.invoke([HumanMessage(content=prompt)])
        if hasattr(response, "content"):
            return response.content.strip()
        if isinstance(response, str):
            return response.strip()
        return str(response).strip()
    except Exception as exc:
        raise RuntimeError(f"Failed to tailor section with LLM: {exc}") from exc


def tailor_complete_resume(main_resume_filename: str, jd_analysis: str) -> Dict[str, Any]:
    version = main_resume_filename.replace(".yaml", "")
    try:
        data = _load_resume(version)
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    result: Dict[str, Any] = {}
    for section in data.get("sections", []):
        section_id = section.get("id")
        markdown = _render_section(section)
        result[section_id] = {
            "original": markdown,
            "tailored": tailor_section_for_jd(f"{version}/{section_id}", markdown, jd_analysis),
        }
    return result


def summarize_resumes_to_index() -> Dict[str, Any]:
    settings = get_settings()
    summary_path = settings.summary_path
    summaries = []
    for version in find_resume_versions():
        data = _load_resume(version)
        metadata = data.get("metadata", {})
        sections = data.get("sections", [])
        summary_bullets: List[str] = []
        skills: List[str] = []
        entries: List[str] = []
        for section in sections:
            section_type = section.get("type")
            if section_type == "summary":
                summary_bullets.extend(section.get("bullets", []))
            elif section_type == "skills":
                for group in section.get("groups", []):
                    skills.extend(group.get("items", []))
            elif section_type in {"experience", "projects"}:
                for entry in section.get("entries", []):
                    title = (entry.get("title") or "").strip()
                    organization = (entry.get("organization") or "").strip()
                    if title and organization:
                        entries.append(f"{title} - {organization}")
                    elif title:
                        entries.append(title)
                    elif organization:
                        entries.append(organization)
        summaries.append(
            {
                "version": version,
                "metadata": {
                    key: metadata.get(key)
                    for key in ["position", "email", "mobile", "github", "linkedin"]
                    if metadata.get(key)
                },
                "highlights": {
                    "summary": _dedupe_preserve_order(summary_bullets, SUMMARY_MAX_BULLETS),
                    "skills": _dedupe_preserve_order(skills, SUMMARY_MAX_SKILLS),
                    "entries": _dedupe_preserve_order(entries, SUMMARY_MAX_ENTRIES),
                },
            }
        )
    payload = {"resumes": summaries}
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
    return {"yaml_path": str(summary_path), "message": f"Summarized {len(summaries)} resumes."}


def read_resume_summary() -> Dict[str, str]:
    summary_path = get_settings().summary_path
    if not summary_path.exists():
        raise FileNotFoundError("File resume_summary.yaml not found.")
    return {"content": summary_path.read_text(encoding="utf-8")}


def aggregate_resumes_to_yaml() -> Dict[str, Any]:  # pragma: no cover - legacy shim
    warnings.warn(
        "aggregate_resumes_to_yaml is deprecated; use summarize_resumes_to_index instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return summarize_resumes_to_index()


def read_aggregated_resumes_yaml() -> Dict[str, str]:  # pragma: no cover - legacy shim
    warnings.warn(
        "read_aggregated_resumes_yaml is deprecated; use read_resume_summary instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return read_resume_summary()


def read_file_content(file_path: str, max_length: int = 0) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    text = path.read_text(encoding="utf-8")
    return text if max_length == 0 else text[:max_length]
