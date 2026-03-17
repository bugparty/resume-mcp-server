from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .repository import _get_section, _load_resume


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
    lines = [f"## {_sanitize_title(section)}"]
    for group in section.get("groups", []):
        category = group.get("category", "Skills")
        items = ", ".join(group.get("items", []))
        lines.append(f"- {category}: {items}")
    return "\n".join(lines)


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


def _render_experience(section: Dict[str, Any]) -> str:
    return _render_entries_common(section)


def _render_projects(section: Dict[str, Any]) -> str:
    lines = [f"## {_sanitize_title(section)}"]
    for entry in section.get("entries", []):
        title = entry.get("title", "Project")
        organization = entry.get("organization", "")
        period = entry.get("period", "")
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
    if not sections:
        return []
    if not isinstance(style, dict):
        return sections

    order = style.get("section_order") if isinstance(style.get("section_order"), list) else []
    disabled_map = (
        style.get("section_disabled")
        if isinstance(style.get("section_disabled"), dict)
        else {}
    )

    def is_enabled(section: Dict[str, Any]) -> bool:
        return disabled_map.get(section.get("id")) is not True

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
    styled_sections = _apply_section_style(data.get("sections", []), data.get("style", {}))
    for section in styled_sections:
        parts.append(_render_section(section))
    return "\n\n".join(filter(None, parts))


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


def _read_section_text_body(version: str, section_id: str) -> str:
    if section_id == HEADER_SECTION_ID:
        data = _load_resume(version)
        return _render_header(data.get("metadata", {}))
    _, section = _get_section(version, section_id)
    return _render_section(section)


def list_modules_in_version(main_resume_filename: str) -> str:
    version = main_resume_filename.replace(".yaml", "")
    try:
        data = _load_resume(version)
    except FileNotFoundError:
        return f"[Error] Resume version not found: {version}"

    sections = data.get("sections", [])
    section_ids = [section.get("id") for section in sections]
    modules_listing = ", ".join(filter(None, section_ids))
    hints: List[str] = [HEADER_SECTION_TEMPLATE]
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
    hints.append("Available modules: " + ("header, " + modules_listing if modules_listing else "header"))
    return "\n\n".join(hints)


def load_resume_section(module_path: str) -> str:
    module_path = module_path.strip()
    if "/" not in module_path:
        module_path = f"resume/{module_path}"
    version, section_id = module_path.split("/", 1)
    try:
        markdown = _read_section_text_body(version, section_id)
    except (FileNotFoundError, KeyError) as exc:
        return f"[Error] {exc}"
    return _editable_text(markdown)


def read_resume_text(target_path: str) -> str:
    try:
        version, section_id = _target_to_version_and_section(target_path)
        if section_id is None:
            return _editable_text(_render_resume_text_body(version))
        return load_resume_section(f"{version}/{section_id}")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return f"[Error] {exc}"


def load_complete_resume(main_resume_filename: str) -> str:
    version = main_resume_filename.replace(".yaml", "")
    try:
        return _render_resume(version)
    except FileNotFoundError as exc:
        return f"[Error] {exc}"
