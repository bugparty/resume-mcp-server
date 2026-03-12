from __future__ import annotations

import copy
import re
import warnings
import os
from typing import Literal
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any
from langchain_core.messages import HumanMessage

from .llm_config import get_llm
from .settings import get_settings
from .filesystem import get_resume_fs
from .resume_input_parser import (
    parse_header_markdown,
    parse_summary_markdown,
    parse_skills_markdown,
    parse_experience_markdown,
    parse_projects_markdown,
    parse_education_markdown,
    parse_raw_markdown,
    SECTION_PARSERS,
)
import rapidfuzz

# Lazily created LLM client (only when needed by tailoring functions)
# Exposed as a module-level name so tests can patch `myagent.resume_loader.llm`.
llm = None


HEADER_SECTION_ID = "header"
HEADER_TITLE = "Header"
METADATA_DISPLAY_ORDER = [
    "first_name",
    "last_name",
    "position",
    "address",
    "mobile",
    "email",
    "github",
    "linkedin",
]

SUMMARY_METADATA_KEYS = ["position", "email", "mobile", "github", "linkedin"]
SUMMARY_MAX_BULLETS = 3
SUMMARY_MAX_SKILLS = 12
SUMMARY_MAX_ENTRIES = 6


def _resume_filename(version: str) -> str:
    """Get the filename for a resume version."""
    return f"{version}.yaml"


def _render_header(metadata: Dict[str, Any]) -> str:
    lines = [f"## {HEADER_TITLE}"]
    added = set()
    for key in METADATA_DISPLAY_ORDER:
        if key in metadata and metadata[key]:
            lines.append(f"{key}: {metadata[key]}")
            added.add(key)
    for key, value in metadata.items():
        if key not in added and value is not None and value != "":
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


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


def _load_temploate_resume() -> Dict[str, Any]:
    yaml_template_path = (
        Path(__file__).parent.parent.parent / "templates" / "resume_template.yaml"
    )
    if not os.path.exists(yaml_template_path):
        raise FileNotFoundError(f"resume yaml template not found")
    with open(yaml_template_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

        # Ensure we always return a dictionary
        if not isinstance(data, dict):
            if data is None:
                raise ValueError(
                    f"Resume template file {yaml_template_path} is empty or contains only null values"
                )
            elif isinstance(data, list):
                raise ValueError(
                    f"Resume template file {yaml_template_path} contains a list at root level, expected a dictionary"
                )
            else:
                raise ValueError(
                    f"Resume template file {yaml_template_path} contains {type(data).__name__} at root level, expected a dictionary"
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
    except Exception:
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


def _summarize_resume(data: Dict[str, Any]) -> Dict[str, Any]:
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

    filtered_metadata = {
        key: metadata.get(key) for key in SUMMARY_METADATA_KEYS if metadata.get(key)
    }

    return {
        "metadata": filtered_metadata,
        "highlights": {
            "summary": _dedupe_preserve_order(summary_bullets, SUMMARY_MAX_BULLETS),
            "skills": _dedupe_preserve_order(skills, SUMMARY_MAX_SKILLS),
            "entries": _dedupe_preserve_order(entries, SUMMARY_MAX_ENTRIES),
        },
    }


def _get_section(
    version: str, section_id: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    data = _load_resume(version)
    for section in data.get("sections", []):
        if section.get("id") == section_id:
            return data, section
    sections = data.get("sections", [])
    sections = [section.get("id") for section in sections]
    all_available_section_ids = ", ".join(sections)
    closer_sections = rapidfuzz.process.extract(section_id, sections, limit=1)
    closer_section_ids = [section[0] for section in closer_sections]
    error_message = f"Section '{section_id}' not found, did you mean '{closer_section_ids[0]}'?, all available section ids are: {all_available_section_ids}"
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


def _sanitize_title(section: Dict[str, Any]) -> str:
    title = section.get("title")
    if title:
        return title
    section_id = section.get("id", "Section")
    return section_id.replace("_", " ").title()


def _render_summary(section: Dict[str, Any]) -> str:
    lines = [f"## {_sanitize_title(section)}"]
    for bullet in section.get("bullets", []):
        lines.append(f"- {bullet}")
    return "\n".join(lines)


def _render_skills(section: Dict[str, Any]) -> str:
    """
    Render the skills section.

    Supports two formats:

    1. format  with bold categories:
    ## Skills
    - **Programming:** Python, JavaScript (Node.js, React), Go, SQL
    - **Cloud Platforms:** AWS, GCP, Docker, Kubernetes
    - **Tools & Practices:** Git, Jenkins, Terraform, Agile/Scrum
    - **Other:** Data analysis, system design, mentoring

    2. format (still supported for parsing):
    ## Skills
    - Programming: Python, JavaScript, Go
    - Cloud Platforms: AWS, GCP, Docker
    """
    lines = [f"## {_sanitize_title(section)}"]
    for group in section.get("groups", []):
        category = group.get("category", "Skills")
        items = ", ".join(group.get("items", []))
        lines.append(f"- {category}: {items}")
    return "\n".join(lines)


def _render_experience(section: Dict[str, Any]) -> str:
    """Render experience section with entries format."""
    return _render_entries_common(section)


def _render_projects(section: Dict[str, Any]) -> str:
    """Render projects section with custom format for projects."""
    lines = [f"## {_sanitize_title(section)}"]
    for entry in section.get("entries", []):
        title = entry.get("title", "Project")
        organization = entry.get("organization", "")
        period = entry.get("period", "")

        # Projects typically use simpler format: Title | Period
        if organization:
            heading = f"### {title} — {organization}"
            if period:
                heading += f" | {period}"
        else:
            heading = f"### {title}"
            if period:
                heading += f" | {period}"

        lines.append(heading)
        for bullet in entry.get("bullets", []):
            lines.append(f"- {bullet}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_education(section: Dict[str, Any]) -> str:
    lines = [f"## {_sanitize_title(section)}"]
    for entry in section.get("entries", []):
        title = entry.get("title", "Degree")
        organization = entry.get("organization", "School")
        period = entry.get("period", "")
        location = entry.get("location", "")

        heading_parts = [title, organization]
        if period:
            heading_parts.append(period)
        if location:
            heading_parts.append(location)

        lines.append("### " + " | ".join(heading_parts))
        for bullet in entry.get("bullets", []):
            lines.append(f"- {bullet}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_entries_common(section: Dict[str, Any]) -> str:
    lines = [f"## {_sanitize_title(section)}"]
    for entry in section.get("entries", []):
        title = entry.get("title", "Role")
        organization = entry.get("organization", "Company")
        location = entry.get("location", "")
        period = entry.get("period", "")
        heading = f"### {title} — {organization}"
        if location:
            heading += f" ({location})"
        if period:
            heading += f" | {period}"
        lines.append(heading)
        for bullet in entry.get("bullets", []):
            lines.append(f"- {bullet}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_raw(section: Dict[str, Any]) -> str:
    title = section.get("title")
    body = section.get("content", "")
    return f"## {title}\n{body}" if title else body


SECTION_RENDERERS = {
    "summary": _render_summary,
    "skills": _render_skills,
    "experience": _render_experience,
    "projects": _render_projects,
    "education": _render_education,
    "raw": _render_raw,
}


def _render_section(section: Dict[str, Any]) -> str:
    renderer = SECTION_RENDERERS.get(section.get("type", "raw"), _render_raw)
    return renderer(section)


def _apply_section_style(
    sections: List[Dict[str, Any]], style: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Reorder/filter sections using style.section_order and style.section_disabled."""

    if not sections:
        return []
    if not isinstance(style, dict):
        return sections

    order = (
        style.get("section_order")
        if isinstance(style.get("section_order"), list)
        else []
    )
    disabled_map = (
        style.get("section_disabled")
        if isinstance(style.get("section_disabled"), dict)
        else {}
    )

    def is_enabled(section: Dict[str, Any]) -> bool:
        section_id = section.get("id")
        return disabled_map.get(section_id) is not True

    section_by_id = {
        section.get("id"): section
        for section in sections
        if isinstance(section, dict) and isinstance(section.get("id"), str)
    }

    ordered: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for section_id in order:
        if not isinstance(section_id, str):
            continue
        section = section_by_id.get(section_id)
        if section is None:
            continue
        if not is_enabled(section):
            seen.add(section_id)
            continue
        ordered.append(section)
        seen.add(section_id)

    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = section.get("id")
        if section_id in seen:
            continue
        if not is_enabled(section):
            if isinstance(section_id, str):
                seen.add(section_id)
            continue
        ordered.append(section)
        if isinstance(section_id, str):
            seen.add(section_id)

    return ordered


def _render_resume(version: str) -> str:
    data = _load_resume(version)
    parts = []
    meta = data.get("metadata", {})
    if meta:
        contact_lines = [
            f"# {meta.get('first_name', '')} {meta.get('last_name', '')}".strip(),
            meta.get("position", ""),
            meta.get("address", ""),
            meta.get("email", ""),
            meta.get("mobile", ""),
            meta.get("github", ""),
            meta.get("linkedin", ""),
        ]
        parts.append("\n".join(line for line in contact_lines if line))
    styled_sections = _apply_section_style(
        data.get("sections", []), data.get("style", {})
    )
    for section in styled_sections:
        parts.append(_render_section(section))
    return "\n\n".join(filter(None, parts))


HEADER_SECTION_TEMPLATE = """Header Section:
        ## Header
        first_name: John
        last_name: Doe
        position: Senior Software Engineer
        address: San Francisco, CA
        mobile: +1-234-567-8900
        email: john.doe@example.com
        github: github.com/johndoe
        linkedin: linkedin.com/in/johndoe"""

SECTION_HINTS_BY_TYPE: Dict[str, str] = {
    "summary": """Summary Section:
        ## Summary
        - 8+ years driving impact across cloud-first products
        - Highlight 3 quantifiable, recruiter-friendly achievements""",
    "skills": """Skills Section:
        ## Skills
        - Programming: Python, TypeScript, Go
        - Cloud Platforms: AWS, GCP, Kubernetes
        - Tooling: Terraform, GitHub Actions, Datadog""",
    "experience": """Experience Section:
        ## Experience
        ### Staff Software Engineer — Acme Corp (Remote) | 2021 - Present
        - Quantify scope, systems owned, and measurable outcomes
        - Lead with action verbs and include stack/tools""",
    "projects": """Projects Section:
        ## Projects
        ### Generative AI Resume Agent — Personal (GitHub) | 2024
        - One-line impact summary mentioning tech stack and result""",
    "education": """Education Section:
        ## Education
        ### M.S. Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA
        - Coursework or honors relevant to the role""",
    "raw": """Custom Section:
        ## Section Title
        Add concise paragraphs or bullets tailored to the role.""",
}

FORMAT_INSTRUCTION_COMMENT = (
    "<!-- Edit the markdown below. Preserve headings and bullet structure so we "
    "can parse updates reliably. -->"
)
MIN_FORMATTED_CONTENT_BYTES = 10
INSERT_POSITIONS = {"start", "end", "before", "after"}


def _non_empty_line_count(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.strip())


def _editable_text(markdown: str) -> str:
    return f"{FORMAT_INSTRUCTION_COMMENT}\n\n{markdown}"


def _strip_instruction_comment(markdown: str) -> str:
    stripped = markdown.strip()
    if stripped.startswith(FORMAT_INSTRUCTION_COMMENT):
        _, _, remainder = stripped.partition("\n\n")
        return remainder.strip()
    return stripped


def _target_to_version_and_section(target_path: str) -> Tuple[str, str | None]:
    normalized = target_path.strip()
    if not normalized:
        raise ValueError("Target path cannot be empty.")
    if "/" not in normalized:
        return normalized, None
    version, section_id = normalized.split("/", 1)
    if not version or not section_id:
        raise ValueError("Target path must be 'version' or 'version/section'.")
    return version, section_id


def _render_resume_text_body(version: str) -> str:
    data = _load_resume(version)
    blocks = [_render_header(data.get("metadata", {}))]
    for section in data.get("sections", []):
        if isinstance(section, dict):
            blocks.append(_render_section(section))
    return "\n\n".join(block for block in blocks if block.strip())


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
            f"[Error] Could not {action} in '{target_path}': {needle_name} was not found. "
            "Call `read_resume_text` first and use a more exact snippet."
        )
    preview = needle[:80].replace("\n", "\\n")
    return (
        f"[Error] Could not {action} in '{target_path}': {needle_name} matched "
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
        header_error = _validate_common_markdown(
            module_path, section_id, HEADER_SECTION_ID, markdown
        )
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
        (
            item
            for item in sections
            if isinstance(item, dict) and item.get("id") == section_id
        ),
        None,
    )
    if section is None:
        raise KeyError(f"Section '{section_id}' not found in version '{version}'")

    section_before = copy.deepcopy(section)
    section_type = section.get("type", "raw")
    _update_section_from_markdown(version, section_id, section, markdown)
    return _validate_parsed_section(
        module_path,
        markdown,
        section_before,
        section,
        section_id,
        section_type,
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
        return (
            f"[Error] Failed to update '{version}': whole-resume editing cannot add, "
            "remove, or reorder top-level '##' blocks."
        )

    working_copy = copy.deepcopy(data)
    for current_section_id, block in zip(expected_section_ids, edited_blocks):
        module_path = (
            f"{version}/{current_section_id}"
            if current_section_id != HEADER_SECTION_ID
            else f"{version}/header"
        )
        error = _apply_section_markdown(
            working_copy,
            version,
            current_section_id,
            block,
            module_path,
        )
        if error:
            return error

    _save_resume(version, working_copy)
    return f"[Success] Updated {version} via editable text view."


def _extract_heading_title(markdown: str) -> str | None:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("##") and not line.startswith("###"):
            return line.lstrip("#").strip().lower()
    return None


def _looks_like_multi_section_resume(markdown: str) -> bool:
    section_headings = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip().startswith("##") and not line.strip().startswith("###")
    ]
    return len(section_headings) > 1


def _has_entry_markers(markdown: str) -> bool:
    return any(
        marker in markdown for marker in ("###", "**")
    ) or bool(re.search(r"^\s*[-*]\s+", markdown, re.MULTILINE))


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
        f"[Error] Failed to parse updated content for '{module_path}'.",
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
    common_error = _validate_common_markdown(
        module_path, section_id, section_type, markdown
    )
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
                module_path,
                section_id,
                section_type,
                "The parsed section became empty.",
                details=details,
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


def list_modules_in_version(main_resume_filename: str) -> str:
    version = main_resume_filename.replace(".yaml", "")
    try:
        data = _load_resume(version)
    except FileNotFoundError:
        return f"[Error] Resume version not found: {version}"

    sections = data.get("sections", [])
    section_ids = [section.get("id") for section in sections]

    modules_listing = ", ".join(filter(None, section_ids))
    header_hint = HEADER_SECTION_TEMPLATE

    hints: List[str] = [header_hint]

    for section in sections:
        section_id = section.get("id", "section")
        section_type = section.get("type", "raw")
        hint = SECTION_HINTS_BY_TYPE.get(section_id) or SECTION_HINTS_BY_TYPE.get(section_type)
        if hint:
            hints.append(f"Module '{section_id}' Hint:\n{hint}")
        else:
            hints.append(
                f"Module '{section_id}' Hint:\n        ## {section.get('title', section_id.title())}\n        Follow the existing structure and keep bullets outcome-focused."
            )

    hints.append(
        "Available modules: "
        + ("header, " + modules_listing if modules_listing else "header")
    )

    return "\n\n".join(hints)


def load_resume_section(module_path: str) -> str:
    module_path = module_path.strip()
    if "/" not in module_path:
        # Backward compatibility: treat bare section id as `resume/<section>`.
        module_path = f"resume/{module_path}"
    version, section_id = module_path.split("/", 1)
    try:
        if section_id == HEADER_SECTION_ID:
            data = _load_resume(version)
            markdown = _render_header(data.get("metadata", {}))
        else:
            _, section = _get_section(version, section_id)
            markdown = _render_section(section)
    except (FileNotFoundError, KeyError) as exc:
        return f"[Error] {exc}"
    return f"{FORMAT_INSTRUCTION_COMMENT}\n\n{markdown}"


def read_resume_text(target_path: str) -> str:
    try:
        version, section_id = _target_to_version_and_section(target_path)
        if section_id is None:
            markdown = _render_resume_text_body(version)
            return _editable_text(markdown)
        return load_resume_section(f"{version}/{section_id}")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return f"[Error] {exc}"


def _read_section_text_body(version: str, section_id: str) -> str:
    if section_id == HEADER_SECTION_ID:
        data = _load_resume(version)
        return _render_header(data.get("metadata", {}))
    _, section = _get_section(version, section_id)
    return _render_section(section)


def _update_section_from_markdown(
    version: str, section_id: str, section: Dict[str, Any], markdown: str
) -> None:
    # First try to match by section_id for specific sections like education
    parser = SECTION_PARSERS.get(section_id)
    
    # If no specific parser for section_id, fall back to type-based lookup
    if parser is None:
        parser = SECTION_PARSERS.get(section.get("type", "raw"), parse_raw_markdown)
    
    parser(markdown, section, version, section_id)


def update_resume_section(module_path: str, new_content: str | None = None) -> str:
    """
    Update a resume section with new Markdown content.

    Args:
        module_path: Version/section identifier (e.g., 'resume/summary')
        new_content: New Markdown content for the section. If omitted, allow
            combined format 'version/section:markdown' in module_path.

    Returns:
        Success or error message
    """
    module_path = module_path.strip()

    # Support combined one-argument format: 'version/section:markdown'
    if new_content is None and ":" in module_path:
        module_path, new_content = module_path.split(":", 1)

    if new_content is None:
        return "[Error] Missing new content for section update."

    new_content = new_content.strip()
    if "/" not in module_path:
        return "[Error] Module path must follow 'version/section' format."
    version, section_id = module_path.split("/", 1)
    try:
        if section_id == HEADER_SECTION_ID:
            header_error = _validate_common_markdown(
                module_path, section_id, HEADER_SECTION_ID, new_content
            )
            if header_error:
                return header_error
            data = _load_resume(version)
            metadata_updates = parse_header_markdown(new_content)
            if not metadata_updates:
                return _build_format_error(
                    module_path,
                    section_id,
                    HEADER_SECTION_ID,
                    "Header content must contain at least one 'key: value' pair.",
                    details="Example: 'email: john.doe@example.com'",
                )
            data.setdefault("metadata", {}).update(metadata_updates)
            _save_resume(version, data)
            return (f"[Success] Updated {module_path}. updated metadata: {metadata_updates}")
        else:
            data, section = _get_section(version, section_id)
            section_before = copy.deepcopy(section)
            section_type = section.get("type", "raw")
            _update_section_from_markdown(
                version, section_id, section, new_content
            )
            validation_error = _validate_parsed_section(
                module_path,
                new_content,
                section_before,
                section,
                section_id,
                section_type,
            )
            if validation_error:
                return validation_error
            # Section is modified in-place by the parser
            _save_resume(version, data)
            result = f"[Success] Updated {module_path}. updated section: {section}"
            if section_before == section:
                result += " No effective content change detected."
            return result
    except (FileNotFoundError, KeyError) as exc:
        return f"[Error] {exc}"


def replace_resume_text(target_path: str, old_text: str, new_text: str) -> str:
    try:
        version, section_id = _target_to_version_and_section(target_path)
        current_text = (
            _render_resume_text_body(version)
            if section_id is None
            else _read_section_text_body(version, section_id)
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return f"[Error] {exc}"

    match_count = _count_matches(current_text, old_text)
    if match_count != 1:
        return _build_match_error(
            "replace text", target_path, "old_text", old_text, match_count
        )

    updated_text = _replace_once(current_text, old_text, new_text)
    return _write_resume_text_body(version, section_id, updated_text)


def insert_resume_text(
    target_path: str,
    new_text: str,
    position: Literal["start", "end", "before", "after"] | str,
    anchor_text: str | None = None,
) -> str:
    try:
        version, section_id = _target_to_version_and_section(target_path)
        current_text = (
            _render_resume_text_body(version)
            if section_id is None
            else _read_section_text_body(version, section_id)
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return f"[Error] {exc}"

    if position not in INSERT_POSITIONS:
        allowed = ", ".join(sorted(INSERT_POSITIONS))
        return f"[Error] Invalid insert position '{position}'. Expected one of: {allowed}."

    if position in {"before", "after"}:
        if not anchor_text:
            return (
                f"[Error] Insert position '{position}' requires `anchor_text` in "
                f"'{target_path}'."
            )
        match_count = _count_matches(current_text, anchor_text)
        if match_count != 1:
            return _build_match_error(
                "insert text", target_path, "anchor_text", anchor_text, match_count
            )
        if position == "before":
            updated_text = _replace_once(current_text, anchor_text, new_text + anchor_text)
        else:
            updated_text = _replace_once(current_text, anchor_text, anchor_text + new_text)
    elif position == "start":
        updated_text = new_text + current_text
    else:
        updated_text = current_text + new_text

    return _write_resume_text_body(version, section_id, updated_text)


def delete_resume_text(target_path: str, old_text: str) -> str:
    try:
        version, section_id = _target_to_version_and_section(target_path)
        current_text = (
            _render_resume_text_body(version)
            if section_id is None
            else _read_section_text_body(version, section_id)
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return f"[Error] {exc}"

    match_count = _count_matches(current_text, old_text)
    if match_count != 1:
        return _build_match_error(
            "delete text", target_path, "old_text", old_text, match_count
        )

    updated_text = _replace_once(current_text, old_text, "")
    return _write_resume_text_body(version, section_id, updated_text)


def update_main_resume(file_name: str, file_content: str) -> str:
    version = file_name.replace(".yaml", "")
    try:
        data = yaml.safe_load(file_content)
    except yaml.YAMLError as exc:
        return f"[Error] Invalid YAML content: {exc}"
    _save_resume(version, data)
    return f"[Success] Replaced resume definition for {version}."


def load_complete_resume(main_resume_filename: str) -> str:
    version = main_resume_filename.replace(".yaml", "")
    try:
        return _render_resume(version)
    except FileNotFoundError as exc:
        return f"[Error] {exc}"


def read_file_content(file_path: str, max_length: int = 0) -> str:
    path = Path(file_path)
    if not path.exists():
        return f"[Error] File not found: {file_path}"
    text = path.read_text(encoding="utf-8")
    return text if max_length == 0 else text[:max_length]


def create_new_version(new_version_name: str) -> str:
    new_version_name = new_version_name.strip()
    if not new_version_name:
        return "[Error] Version name cannot be empty."
    target_filename = _resume_filename(new_version_name)
    resume_fs = get_resume_fs()
    if resume_fs.exists(target_filename):
        return f"[Error] Version '{new_version_name}' already exists."

    # Load standard template from templates directory
    template_path = (
        Path(__file__).resolve().parents[2] / "templates" / "resume_template.yaml"
    )
    if not template_path.exists():
        return "[Error] Standard resume template not found at templates/resume_template.yaml."

    try:
        with template_path.open("r", encoding="utf-8") as handle:
            base = yaml.safe_load(handle)
        _save_resume(new_version_name, base)
        return f"[Success] Created new resume version '{new_version_name}' from standard template."
    except Exception as e:
        return f"[Error] Failed to load template: {str(e)}"


def tailor_section_for_jd(
    module_path: str, section_content: str, jd_analysis: str
) -> str:
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
        return f"[Error] Failed to tailor section with LLM: {exc}"


def tailor_complete_resume(
    main_resume_filename: str, jd_analysis: str
) -> Dict[str, Any]:
    version = main_resume_filename.replace(".yaml", "")
    try:
        data = _load_resume(version)
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    result: Dict[str, Any] = {}
    for section in data.get("sections", []):
        section_id = section.get("id")
        markdown = _render_section(section)
        tailored = tailor_section_for_jd(
            f"{version}/{section_id}", markdown, jd_analysis
        )
        result[section_id] = {"original": markdown, "tailored": tailored}
    return result


def summarize_resumes_to_index() -> Dict[str, Any]:
    settings = get_settings()
    summary_path = settings.summary_path
    summaries = []

    for version in find_resume_versions():
        data = _load_resume(version)
        summary = _summarize_resume(data)
        summary["version"] = version
        summaries.append(summary)

    payload = {"resumes": summaries}
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)

    return {
        "yaml_path": str(summary_path),
        "message": f"Summarized {len(summaries)} resumes.",
    }


def read_resume_summary() -> Dict[str, str]:
    summary_path = get_settings().summary_path
    if not summary_path.exists():
        return {"content": "[Error] File resume_summary.yaml not found."}
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


def load_complete_resume_as_dict(version: str) -> Dict[str, Any]:
    return _load_resume(version)
