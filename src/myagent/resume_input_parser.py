"""
Resume Input Parser Module

This module handles parsing of Markdown input for resume sections.
It converts user-edited Markdown back into structured YAML data.
"""

from __future__ import annotations

import re
import logging
import json
import copy
from pathlib import Path
from typing import Dict, List, Any
from functools import wraps

from .settings import get_settings

# Configure logging for markdown parsing operations
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
SETTINGS = get_settings()
LOGS_DIR = SETTINGS.logs_dir
LOGS_DIR.mkdir(parents=True, exist_ok=True)

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


# Regular expressions for parsing entry headings
# eg ### Software Engineer — OpenAI (San Francisco, CA) | 2020 - Present
ENTRY_HEADING_RE = re.compile(
    r"^###\s+(?P<title>[^—]+?)\s+—\s+(?P<organization>[^(|]+?)(?:\s+\((?P<location>[^)]+)\))?(?:\s+\|\s+(?P<period>.*))?$"
)
# eg ### Software Engineer | OpenAI | 2020 - Present | San Francisco, CA
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


def parse_header_markdown(markdown: str) -> Dict[str, Any]:
    """Parse header section markdown into metadata dictionary.
    
    Args:
        markdown: Markdown text containing key: value pairs
        
    Returns:
        Dictionary of metadata key-value pairs
    """
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


# Education format regexes
# eg **M.S. Computer Science**, Stanford University | 2016 - 2018
EDUCATION_BOLD_RE = re.compile(
    r"^\*\*(?P<degree>[^*]+)\*\*,?\s*(?P<university>[^|]+?)(?:\s+\|\s+(?P<period>.*))?$"
)
# eg ### M.S. Computer Science — Stanford University (California) | 2016 - 2018
EDUCATION_HEADING_RE = re.compile(
    r"^###\s+(?P<degree>[^—]+?)\s+—\s+(?P<university>[^(|]+?)(?:\s+\((?P<location>[^)]+)\))?(?:\s+\|\s+(?P<period>.*))?$"
)


@log_markdown_parsing
def parse_education_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse education section markdown into structured data.

    Supports multiple formats:

    1. Bold format with degree and university:
        ## Education
        **M.S. Computer Science**, Stanford University | 2016 - 2018
        - Coursework or honors relevant to the role
        - GPA: 3.9/4.0

    2. Standard heading format:
        ## Education
        ### M.S. Computer Science — Stanford University (California) | 2016 - 2018
        - Relevant coursework or achievements
        - GPA or academic honors if applicable

    3. Standard experience-like format:
        ## Education
        ### Bachelor of Science in Computer Science — MIT (Cambridge, MA) | 2012 - 2016
        - Major GPA: 3.8/4.0
        - Relevant coursework: Algorithms, Machine Learning, Databases

    Args:
        markdown: Markdown text with education entries
        section: Section dictionary to update in-place
        version: Resume version identifier
        section_id: Section identifier
    """
    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    pending_degree: str | None = None  # Track degree from previous line

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Parse section title (## Education)
        if stripped.startswith("##") and not stripped.startswith("###"):
            section["title"] = stripped.lstrip("#").strip()
            continue

        # Parse education entries with ### heading format
        if stripped.startswith("###"):
            # Save previous entry if exists
            if current:
                entries.append(current)
                current = None
            pending_degree = None

            # Try standard heading format: ### Degree — University (Location) | Period
            match = EDUCATION_HEADING_RE.match(stripped)
            if match:
                current = {
                    "title": match.group("degree").strip(),
                    "organization": match.group("university").strip(),
                    "location": (match.group("location") or "").strip(),
                    "period": (match.group("period") or "").strip(),
                    "bullets": [],
                }
                continue

            # If no regex matches, try generic entry format
            match = ENTRY_HEADING_RE.match(stripped)
            if not match:
                match = ENTRY_HEADING_PIPE_RE.match(stripped)
            if match:
                current = {
                    "title": match.group("title").strip(),
                    "organization": match.group("organization").strip(),
                    "location": (match.group("location") or "").strip(),
                    "period": (match.group("period") or "").strip(),
                    "bullets": [],
                }
                continue

            logger.error(f"Failed to match education heading: {stripped}")
            continue

        # Parse bold format: **Degree**, University | Period (single line)
        if stripped.startswith("**") and "**" in stripped[2:]:
            match = EDUCATION_BOLD_RE.match(stripped)
            if match:
                # Save previous entry if exists
                if current:
                    entries.append(current)
                    
                current = {
                    "title": match.group("degree").strip(),
                    "organization": match.group("university").strip(),
                    "location": "",  # Bold format typically doesn't include location
                    "period": (match.group("period") or "").strip(),
                    "bullets": [],
                }
                pending_degree = None
                continue
            else:
                # Maybe it's a two-line format: **Degree** on one line
                # Extract degree and wait for next line with university
                degree_match = re.match(r"^\*\*(?P<degree>[^*]+)\*\*\s*$", stripped)
                if degree_match:
                    # Save previous entry if exists
                    if current:
                        entries.append(current)
                        current = None
                    pending_degree = degree_match.group("degree").strip()
                    continue
                else:
                    logger.error(f"Failed to match bold education entry: {stripped}")
                    continue

        # If we have a pending degree, check if this line has university info
        if pending_degree:
            # Try to match: University | Period
            univ_match = re.match(r"^(?P<university>[^|]+?)(?:\s+\|\s+(?P<period>.*))?$", stripped)
            if univ_match and not stripped.startswith("-"):
                current = {
                    "title": pending_degree,
                    "organization": univ_match.group("university").strip(),
                    "location": "",
                    "period": (univ_match.group("period") or "").strip(),
                    "bullets": [],
                }
                pending_degree = None
                continue

        # Parse bullet points
        if stripped.startswith("-") and current is not None:
            current.setdefault("bullets", []).append(stripped[1:].strip())

    # Don't forget the last entry
    if current:
        entries.append(current)

    section["entries"] = entries

@log_markdown_parsing
def parse_summary_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse summary section markdown into structured data.
    
    Args:
        markdown: Markdown text with title and bullet points
        section: Section dictionary to update in-place
        version: Resume version identifier
        section_id: Section identifier
    """
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
def parse_skills_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse skills section markdown into structured data.

    Supports two formats:
    1. New format: - **Programming:** Python, JavaScript, Go
    2. Old format: - Programming: Python, JavaScript, Go
    
    Args:
        markdown: Markdown text with categorized skill lists
        section: Section dictionary to update in-place
        version: Resume version identifier
        section_id: Section identifier
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


@log_markdown_parsing
def parse_experience_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse experience section markdown into structured data.

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
        markdown: Markdown text with experience entries
        section: Section dictionary to update in-place
        version: Resume version identifier
        section_id: Section identifier
    """
    # Import here to avoid circular dependency
    from .resume_loader import _load_temploate_resume
    
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


@log_markdown_parsing
def parse_projects_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse projects section markdown into structured data.

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
        markdown: Markdown text with project entries
        section: Section dictionary to update in-place
        version: Resume version identifier
        section_id: Section identifier
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


@log_markdown_parsing
def parse_raw_markdown(
    markdown: str, section: Dict[str, Any], version: str, section_id: str
) -> None:
    """Parse raw/custom section markdown into structured data.
    
    Args:
        markdown: Markdown text with optional title and content
        section: Section dictionary to update in-place
        version: Resume version identifier
        section_id: Section identifier
    """
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("#"):
        section["title"] = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:])
    else:
        body = markdown.strip()
    section["content"] = body.strip()


# Mapping of section types to their parser functions
SECTION_PARSERS = {
    "summary": parse_summary_markdown,
    "skills": parse_skills_markdown,
    "entries": parse_experience_markdown,  # Deprecated, use experience/projects instead
    "experience": parse_experience_markdown,
    "projects": parse_projects_markdown,
    "education": parse_education_markdown,
    "raw": parse_raw_markdown,
}
