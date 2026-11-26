from __future__ import annotations

from typing import Any, Dict, List

from .layout import apply_layout
from .repository import get_section, load_resume


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
PREVIEW_CONTACT_FIELDS = (
    "position",
    "address",
    "email",
    "mobile",
    "github",
    "linkedin",
)

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
SECTION_HINTS_BY_TYPE["entries"] = SECTION_HINTS_BY_TYPE["experience"]

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


def format_hint(section_id: str, section_type: str = "raw") -> str:
    """Markdown example showing the structure a section update must follow."""
    if section_id == HEADER_SECTION_ID:
        return HEADER_SECTION_TEMPLATE
    return (
        SECTION_HINTS_BY_TYPE.get(section_id)
        or SECTION_HINTS_BY_TYPE.get(section_type)
        or SECTION_HINTS_BY_TYPE["raw"]
    )


def editable_text(markdown: str) -> str:
    """Wrap markdown with the instruction comment shown to editors."""
    return f"{FORMAT_INSTRUCTION_COMMENT}\n\n{markdown}"


def strip_instruction_comment(markdown: str) -> str:
    stripped = markdown.strip()
    if stripped.startswith(FORMAT_INSTRUCTION_COMMENT):
        return stripped[len(FORMAT_INSTRUCTION_COMMENT) :].strip()
    return stripped


def render_text_body(data: Dict[str, Any]) -> str:
    """Whole-resume editable markdown: header block + every section, in
    document order (layout is ignored so edits map 1:1 onto sections)."""
    blocks = [_render_header(data.get("metadata") or {})]
    blocks.extend(
        _render_section(section)
        for section in data.get("sections") or []
        if isinstance(section, dict)
    )
    return "\n\n".join(block for block in blocks if block.strip())


def render_section_body(version_name: str, section_id: str) -> str:
    """Editable markdown for one section (or the ``header`` pseudo-section)."""
    if section_id == HEADER_SECTION_ID:
        return _render_header(load_resume(version_name).get("metadata") or {})
    _, section = get_section(version_name, section_id)
    return _render_section(section)


def read_resume_text(version_name: str, section_id: str | None = None) -> str:
    """Editable markdown for a whole version, or a single section."""
    if section_id is None:
        body = render_text_body(load_resume(version_name))
    else:
        body = render_section_body(version_name, section_id)
    return editable_text(body)


def render_resume_markdown(version_name: str) -> str:
    """Read-only Markdown preview of a version with its layout applied."""
    data = load_resume(version_name)
    parts = []
    meta = data.get("metadata") or {}
    if meta:
        name = f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
        contact = [
            f"# {name}" if name else "",
            *(meta.get(key, "") for key in PREVIEW_CONTACT_FIELDS),
        ]
        parts.append("\n".join(line for line in contact if line))
    for section in apply_layout(data.get("sections") or [], data.get("style")):
        parts.append(_render_section(section))
    return "\n\n".join(filter(None, parts))


def list_sections(version_name: str) -> List[Dict[str, Any]]:
    """Describe every editable section, including the ``header`` block."""
    data = load_resume(version_name)
    disabled = (data.get("style") or {}).get("section_disabled") or {}
    sections: List[Dict[str, Any]] = [
        {
            "id": HEADER_SECTION_ID,
            "type": HEADER_SECTION_ID,
            "title": HEADER_TITLE,
            "enabled": True,
            "format_hint": HEADER_SECTION_TEMPLATE,
        }
    ]
    for section in data.get("sections") or []:
        if not isinstance(section, dict) or not isinstance(section.get("id"), str):
            continue
        section_id = section["id"]
        section_type = section.get("type", "raw")
        sections.append(
            {
                "id": section_id,
                "type": section_type,
                "title": _sanitize_title(section),
                "enabled": disabled.get(section_id) is not True,
                "format_hint": format_hint(section_id, section_type),
            }
        )
    return sections
