from __future__ import annotations

import warnings
import os
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
        elif section_type == "entries" and section.get("id") in {
            "experience",
            "projects",
        }:
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


def set_section_visibility(version_name: str, section_id: str, enabled: bool) -> Dict[str, Any]:
    """Update style.section_disabled for a given section id.

    Returns a dict with updated style block for callers to format.
    """

    version_name = _require_version_name(version_name)
    data = _load_resume(version_name)
    sections = data.get("sections") or []
    if not any(isinstance(s, dict) and s.get("id") == section_id for s in sections):
        raise KeyError(f"Section '{section_id}' not found in version '{version_name}'")

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
    _save_resume(version_name, data)
    return {"style": style}


def set_section_order(version_name: str, order: List[str]) -> Dict[str, Any]:
    """Replace style.section_order with the provided list (filtered to known ids)."""

    version_name = _require_version_name(version_name)
    data = _load_resume(version_name)
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
    _save_resume(version_name, data)
    return {"style": style, "skipped_ids": [sid for sid in order if sid not in known_set]}


def _require_version_name(version_name: str) -> str:
    version_name = (version_name or "").strip()
    if not version_name:
        raise ValueError("version_name cannot be empty")
    if version_name.endswith(".yaml"):
        raise ValueError("version_name must not include the .yaml suffix")
    return version_name


def get_resume_layout(version_name: str) -> Dict[str, Any]:
    """Return the current layout settings (order/disabled) for a resume version."""

    version_name = _require_version_name(version_name)
    data = _load_resume(version_name)
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


def _render_entries(section: Dict[str, Any]) -> str:
    """Render generic entries section (deprecated, use experience/projects instead)."""
    return _render_entries_common(section)


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
    "entries": _render_entries,  # Deprecated, use experience/projects instead
    "experience": _render_experience,
    "projects": _render_projects,
    "raw": _render_raw,
}


def _render_section(section: Dict[str, Any]) -> str:
    renderer = SECTION_RENDERERS.get(section.get("type", "raw"), _render_raw)
    return renderer(section)


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
    for section in data.get("sections", []):
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
        **M.S. Computer Science**, Stanford University | 2016 - 2018
        - Coursework or honors relevant to the role""",
    "raw": """Custom Section:
        ## Section Title
        Add concise paragraphs or bullets tailored to the role.""",
}


def list_modules_in_version(version_name: str) -> str:
    """Return section hints and a listing of section ids for a resume version."""

    try:
        version = _require_version_name(version_name)
    except ValueError as exc:
        return f"[Error] {exc}"
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

def get_resume_section(version_name: str, section_id: str) -> str:
    """Load the Markdown content of a resume section by (version_name, section_id)."""

    try:
        version = _require_version_name(version_name)
    except ValueError as exc:
        return f"[Error] {exc}"

    section_id = (section_id or "").strip()
    if not section_id:
        return "[Error] section_id cannot be empty."

    try:
        if section_id == HEADER_SECTION_ID:
            data = _load_resume(version)
            markdown = _render_header(data.get("metadata", {}))
        else:
            _, section = _get_section(version, section_id)
            markdown = _render_section(section)
    except (FileNotFoundError, KeyError) as exc:
        return f"[Error] {exc}"
    instructions = "<!-- Edit the markdown below. Preserve headings and bullet structure so we can parse updates reliably. -->"
    return f"{instructions}\n\n{markdown}"


def _update_section_from_markdown(
    version: str, section_id: str, section: Dict[str, Any], markdown: str
) -> None:
    # First try to match by section_id for specific sections like education
    # This allows education to use entries type but have custom parsing
    parser = SECTION_PARSERS.get(section_id)
    
    # If no specific parser for section_id, fall back to type-based lookup
    if parser is None:
        parser = SECTION_PARSERS.get(section.get("type", "raw"), parse_raw_markdown)
    
    parser(markdown, section, version, section_id)


def update_resume_section(version_name: str, section_id: str, new_content: str) -> str:
    """
    Update a resume section with new Markdown content.

    Args:
        version_name: Resume version name (e.g., 'resume')
        section_id: Section identifier (e.g., 'summary', 'experience')
        new_content: New Markdown content for the section

    Returns:
        Success or error message
    """
    version_name = version_name.strip()
    section_id = section_id.strip()
    new_content = new_content.strip()
    
    if not new_content:
        return "[Error] Missing new content for section update."
    
    try:
        if section_id == HEADER_SECTION_ID:
            data = _load_resume(version_name)
            metadata_updates = parse_header_markdown(new_content)
            if not metadata_updates:
                return "[Error] Header content must contain at least one 'key: value' pair."
            data.setdefault("metadata", {}).update(metadata_updates)
            _save_resume(version_name, data)
            return (f"[Success] Updated {version_name}/{section_id}. updated metadata: {metadata_updates}")
        else:
            data, section = _get_section(version_name, section_id)
            _update_section_from_markdown(
                version_name, section_id, section, new_content
            )
            # Section is modified in-place by the parser
            _save_resume(version_name, data)
            return (f"[Success] Updated {version_name}/{section_id}. updated section: {section}")
    except (FileNotFoundError, KeyError) as exc:
        return f"[Error] {exc}"


def update_main_resume(version_name: str, file_content: str) -> str:
    try:
        version = _require_version_name(version_name)
    except ValueError as exc:
        return f"[Error] {exc}"
    try:
        data = yaml.safe_load(file_content)
    except yaml.YAMLError as exc:
        return f"[Error] Invalid YAML content: {exc}"
    _save_resume(version, data)
    return f"[Success] Replaced resume definition for {version}."


def load_complete_resume(version_name: str) -> str:
    """Render a full resume version as Markdown."""

    try:
        version = _require_version_name(version_name)
    except ValueError as exc:
        return f"[Error] {exc}"
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
    version_name: str, section_id: str, section_content: str, jd_analysis: str
) -> str:
    try:
        version_name = _require_version_name(version_name)
    except ValueError as exc:
        return f"[Error] {exc}"

    section_id = (section_id or "").strip()
    if not section_id:
        return "[Error] section_id cannot be empty."

    prompt = f"""
You are updating a resume section stored as Markdown. Preserve the existing heading structure and bullet formatting while tailoring the content to match the job description analysis.

Resume Version: {version_name}
Section Id: {section_id}

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
