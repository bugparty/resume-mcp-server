from __future__ import annotations

import re
import warnings
import logging
import json
import copy
from pathlib import Path
from typing import Dict, List, Tuple, Any
from functools import wraps
import os
import yaml
from langchain_core.messages import HumanMessage

from .llm_config import get_llm
from .settings import get_settings
from .filesystem import get_resume_fs
import rapidfuzz

# Lazily created LLM client (only when needed by tailoring functions)
# Exposed as a module-level name so tests can patch `myagent.resume_loader.llm`.
llm = None

# Configure logging for markdown parsing operations
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# File handler for markdown parse logs
markdown_log_file = LOGS_DIR / "markdown_parsing.log"
file_handler = logging.FileHandler(markdown_log_file, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Console handler for debugging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)

# Formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def log_markdown_parsing(func):
    """
    Decorator to log markdown parsing operations.
    Records input markdown and section changes.
    """

    @wraps(func)
    def wrapper(
        markdown: str, section: Dict[str, Any], version: str, section_id: str
    ) -> None:
        func_name = func.__name__

        # Create a deep copy of the section before parsing
        section_before = copy.deepcopy(section)

        # Log input
        logger.info(f"=== {func_name} START ===")
        logger.info(f"Version: {version}, Section ID: {section_id}")
        logger.info(f"Input markdown:\n{markdown}")
        logger.info(
            f"Section before parsing: {json.dumps(section_before, ensure_ascii=False, indent=2)}"
        )

        try:
            # Execute the actual parsing function
            result = func(markdown, section, version, section_id)

            # Log the changes
            logger.info(
                f"Section after parsing: {json.dumps(section, ensure_ascii=False, indent=2)}"
            )

            # Log what changed
            changed_fields = []
            for key in set(list(section_before.keys()) + list(section.keys())):
                before_val = section_before.get(key)
                after_val = section.get(key)
                if before_val != after_val:
                    changed_fields.append(key)
                    logger.info(f"Field '{key}' changed:")
                    logger.info(
                        f"  Before: {json.dumps(before_val, ensure_ascii=False)}"
                    )
                    logger.info(
                        f"  After:  {json.dumps(after_val, ensure_ascii=False)}"
                    )

            if not changed_fields:
                logger.info("No fields were modified")
            else:
                logger.info(f"Modified fields: {', '.join(changed_fields)}")

            logger.info(f"=== {func_name} END ===\n")

            return result

        except Exception as e:
            logger.error(f"Error in {func_name}: {str(e)}", exc_info=True)
            raise

    return wrapper


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


def _parse_header_markdown(markdown: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


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


def list_modules_in_version(main_resume_filename: str) -> str:
    version = main_resume_filename.replace(".yaml", "")
    try:
        data = _load_resume(version)
    except FileNotFoundError:
        return f"[Error] Resume version not found: {version}"
    section_ids = [section.get("id") for section in data.get("sections", [])]
    return ", ".join(section_ids)


def load_resume_section(module_path: str) -> str:
    module_path = module_path.strip()
    if "/" not in module_path:
        return "[Error] Module path must follow 'version/section' format."
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
    instructions = "<!-- Edit the markdown below. Preserve headings and bullet structure so we can parse updates reliably. -->"
    return f"{instructions}\n\n{markdown}"


@log_markdown_parsing
def _parse_summary_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    bullets: List[str] = []
    for line in lines:
        if line.startswith("#"):
            section["title"] = line.lstrip("#").strip()
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "*")):
            bullets.append(stripped[1:].strip())
        else:
            bullets.append(stripped)
    section["bullets"] = bullets


@log_markdown_parsing
def _parse_skills_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """
    Parse skills markdown content.

    Supports two formats:
    1. New format: - **Programming:** Python, JavaScript, Go
    2. Old format: - Programming: Python, JavaScript, Go
    """
    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    groups: List[Dict[str, Any]] = []
    for line in lines:
        if line.startswith("#"):
            section["title"] = line.lstrip("#").strip()
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("-"):
            continue
        content = stripped[1:].strip()
        if ":" in content:
            category, items = content.split(":", 1)
            # Handle bold formatting in category (remove ** if present)
            category = category.strip()
            if category.startswith("**") and "**" in category:
                # Find the end of the bold formatting
                end_pos = category.find("**", 2)
                if end_pos != -1:
                    category = category[2:end_pos].strip()
                else:
                    # If no closing **, just remove the opening **
                    category = category[2:].strip()

            # Clean up items and remove any bold formatting
            item_list = []
            for item in re.split(r",|;", items):
                cleaned_item = item.strip()
                # Remove ** from items if present
                if cleaned_item.startswith("**"):
                    cleaned_item = cleaned_item[2:].strip()
                if cleaned_item.endswith("**"):
                    cleaned_item = cleaned_item[:-2].strip()
                if cleaned_item:
                    item_list.append(cleaned_item)
        else:
            category = content
            # Handle bold formatting in category (remove ** if present)
            if category.startswith("**") and category.endswith("**"):
                category = category[2:-2].strip()
            item_list = []
        groups.append({"category": category.strip(), "items": item_list})
    section["groups"] = groups


# eg ### 软件工程师 — OpenAI (San Francisco, CA) | 2020 - Present
ENTRY_HEADING_RE = re.compile(
    r"^###\s+(?P<title>[^—]+?)\s+—\s+(?P<organization>[^(|]+?)(?:\s+\((?P<location>[^)]+)\))?(?:\s+\|\s+(?P<period>.*))?$"
)
# eg ### 软件工程师 | OpenAI | 2020 - Present | San Francisco, CA
ENTRY_HEADING_PIPE_RE = re.compile(
    r"^###\s+(?P<title>[^|]+?)\s*\|\s*(?P<organization>[^|]+?)\s*\|\s*(?P<period>[^|]+?)\s*\|\s*(?P<location>.+)$"
)
# New regex for quoted format: '**Job Title | Company Name | Time Period**'
ENTRY_QUOTED_RE = re.compile(
    r"^['\"]?\*\*(?P<title>[^|]+?)\s*\|\s*(?P<organization>[^|]+?)(?:\s*\|\s*(?P<period>[^*]+?))?\*\*['\"]?$"
)

# Projects format regexes
# eg ### Project Title | Period (simple format, no organization)
PROJECT_SIMPLE_RE = re.compile(r"^###\s+(?P<title>[^|]+?)\s*\|\s*(?P<period>.+)$")
# eg ### Project Title — Organization | Period (with organization)
PROJECT_WITH_ORG_RE = re.compile(
    r"^###\s+(?P<title>[^—]+?)\s+—\s+(?P<organization>[^|]+?)(?:\s+\|\s+(?P<period>.*))?$"
)

@log_markdown_parsing
def _parse_experience_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse experience section markdown."""
    """
    Parses the markdown for entries and updates the section accordingly.

    Supports two formats:

    1. Standard format with ### headers:
        ## Experience
        ### Job Title — Company Name (Location) | Start Date - End Date
        - Bullet point 1
        - Bullet point 2
        - Bullet point 3
        ### Job Title — Company Name (Location) | Start Date - End Date
        - Bullet point 1

    2. Quoted format with bold text:
        ## Experience
        '**Software Engineer | NovaTech Solutions | 2020 - Present**'
        - Bullet point 1
        - Bullet point 2
        - Bullet point 3

    Args:
        markdown: The markdown to parse.
        section: The section to update.
        version: The resume version.
        section_id: The section identifier.
    """
    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    template_data = _load_temploate_resume()
    section_ids = [section["id"] for section in template_data.get("sections", [])]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("##") and not stripped.startswith("###"):
            section["title"] = stripped.lstrip("#").strip()
            # entry["id"] = rapidfuzz.process.extract(entry["title"], section_ids, limit=1)[0][0]
            continue
        if stripped.startswith("###"):
            match = ENTRY_HEADING_RE.match(stripped)
            if not match:
                match = ENTRY_HEADING_PIPE_RE.match(stripped)
            if not match:
                logger.error(f"Failed to match entry heading: {stripped}")
                continue
            if current:
                entries.append(current)
            current = {
                "title": match.group("title").strip(),
                "organization": match.group("organization").strip(),
                "location": (match.group("location") or "").strip(),
                "period": (match.group("period") or "").strip(),
                "bullets": [],
            }

            continue

        # Check for quoted format: '**Job Title | Company Name | Time Period**'
        quoted_match = ENTRY_QUOTED_RE.match(stripped)
        if quoted_match:
            if current:
                entries.append(current)

            current = {
                "title": quoted_match.group("title").strip(),
                "organization": quoted_match.group("organization").strip(),
                "location": "",  # No location in this format
                "period": (quoted_match.group("period") or "").strip(),
                "bullets": [],
            }
            continue
        if stripped.startswith("-") and current is not None:
            current.setdefault("bullets", []).append(stripped[1:].strip())
    if current:
        entries.append(current)

    section["entries"] = entries
    return section


@log_markdown_parsing
def _parse_projects_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse projects section markdown.

    Supports multiple formats:

    1. Simple format with title and period only:
        ## Projects
        ### Intelligent Recommendation Engine Optimization | 2021
        - Combined collaborative filtering with deep learning for personalized feeds.
        - Deployed in short-video app, increasing user retention by 12%.

    2. Format with organization:
        ## Projects
        ### Project Title — Organization | 2023
        - Project description and achievements

    Args:
        markdown: The markdown to parse.
        section: The section to update.
        version: The resume version.
        section_id: The section identifier.
    """
    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Parse section title (## Projects)
        if stripped.startswith("##") and not stripped.startswith("###"):
            section["title"] = stripped.lstrip("#").strip()
            continue

        # Parse project entries (### ...)
        if stripped.startswith("###"):
            # Save previous entry if exists
            if current:
                entries.append(current)

            # Try format with organization first: ### Title — Organization | Period
            match = PROJECT_WITH_ORG_RE.match(stripped)
            if match:
                current = {
                    "title": match.group("title").strip(),
                    "organization": match.group("organization").strip(),
                    "location": "",  # Projects typically don't have location
                    "period": (match.group("period") or "").strip(),
                    "bullets": [],
                }
                continue

            # Try simple format: ### Title | Period
            match = PROJECT_SIMPLE_RE.match(stripped)
            if match:
                current = {
                    "title": match.group("title").strip(),
                    "organization": "",  # No organization in simple format
                    "location": "",
                    "period": match.group("period").strip(),
                    "bullets": [],
                }
                continue

            # If no regex matches, log error
            logger.error(f"Failed to match project heading: {stripped}")
            continue

        # Parse bullet points
        if stripped.startswith("-") and current is not None:
            current.setdefault("bullets", []).append(stripped[1:].strip())

    # Don't forget the last entry
    if current:
        entries.append(current)

    section["entries"] = entries
    return section


@log_markdown_parsing
def _parse_raw_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("#"):
        section["title"] = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:])
    else:
        body = markdown.strip()
    section["content"] = body.strip()


SECTION_PARSERS = {
    "summary": _parse_summary_markdown,
    "skills": _parse_skills_markdown,
    "entries": _parse_experience_markdown,  # Deprecated, use experience/projects instead
    "experience": _parse_experience_markdown,
    "projects": _parse_projects_markdown,
    "raw": _parse_raw_markdown,
}


def _update_section_from_markdown(
    version: str, section_id: str, section: Dict[str, Any], markdown: str
) -> None:
    parser = SECTION_PARSERS.get(section.get("type", "raw"), _parse_raw_markdown)
    section = parser(markdown, section, version, section_id)
    return section


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
            data = _load_resume(version)
            metadata_updates = _parse_header_markdown(new_content)
            if not metadata_updates:
                return "[Error] Header content must contain at least one 'key: value' pair."
            data.setdefault("metadata", {}).update(metadata_updates)
            _save_resume(version, data)
            return (f"[Success] Updated {module_path}. updated metadata: {metadata_updates}")
        else:
            data, section = _get_section(version, section_id)
            updated_section = _update_section_from_markdown(
                version, section_id, section, new_content
            )
            # _update_section_by_id(version, section_id, updated_section)
            _save_resume(version, data)
            return (f"[Success] Updated {module_path}. updated section: {updated_section}")
    except (FileNotFoundError, KeyError) as exc:
        return f"[Error] {exc}"


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
