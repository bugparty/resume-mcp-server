from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from resume_platform.models.agent_resume import SectionType
from resume_platform.paths import LATEX_TEMPLATE_DIR
from resume_platform.resume.layout import apply_layout
from resume_platform.resume.repository import load_resume

DEFAULT_LATEX_COMPILE_API_URL = "https://latex-compile.k.0x1f0c.dev"

# Setup logging
logger = logging.getLogger(__name__)


UNICODE_LATEX_TOKENS = {
    "×": "@@TEXTTIMES@@",
    "•": "@@TEXTBULLET@@",
    "…": "@@TEXTELLIPSIS@@",
    "·": "@@TEXTMDOT@@",
    "· ": "@@TEXTMDOT@@",  # with trailing space
}

UNICODE_SIMPLE_REPLACEMENTS = {
    "–": "--",
    "—": "---",
    "−": "-",
    "‑": "-",  # non-breaking hyphen
    "“": "``",
    "”": "''",
    "‘": "`",
    "’": "'",
}


def _preprocess_unicode(text: str) -> str:
    for char, replacement in UNICODE_SIMPLE_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    for char, token in UNICODE_LATEX_TOKENS.items():
        text = text.replace(char, token)
    return text


def _restore_unicode_tokens(text: str) -> str:
    replacements = {
        "@@TEXTTIMES@@": r"$\times$",
        "@@TEXTBULLET@@": r"\textbullet",
        "@@TEXTELLIPSIS@@": r"\ldots",
        "@@TEXTMDOT@@": r"\textperiodcentered",
    }
    for token, latex in replacements.items():
        text = text.replace(token, latex)
    return text


def _extract_github_handle(value: str) -> str:
    raw = value.strip()
    if not raw:
        return raw

    lower = raw.lower()
    candidate = raw
    if lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(raw)
    else:
        parsed = urlparse("https://" + raw)

    if parsed.netloc and parsed.netloc.lower().endswith("github.com"):
        path = parsed.path.strip("/")
        if path:
            return path.split("/")[0]

    if candidate.lower().startswith("github.com/"):
        remainder = candidate.split("/", 1)[1]
        return remainder.split("/")[0]

    return raw


def _extract_linkedin_slug(value: str) -> str:
    raw = value.strip()
    if not raw:
        return raw

    lower = raw.lower()
    candidate = raw
    if lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(raw)
    else:
        parsed = urlparse("https://" + raw)

    if parsed.netloc:
        netloc = parsed.netloc.lower()
        if netloc.endswith("linkedin.com"):
            path = parsed.path.strip("/")
            if path:
                segments = path.split("/")
                if segments[0] == "in" and len(segments) >= 2:
                    return segments[1]
                return segments[-1]

    if candidate.lower().startswith("linkedin.com/"):
        remainder = candidate.split("/", 1)[1]
        parts = remainder.split("/")
        if parts and parts[0].lower() == "in" and len(parts) >= 2:
            return parts[1]
        return parts[-1]

    return raw


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    if not metadata:
        return metadata

    normalized = dict(metadata)
    github_value = metadata.get("github")
    if isinstance(github_value, str) and github_value.strip():
        normalized["github"] = _extract_github_handle(github_value)
    linkedin_value = metadata.get("linkedin")
    if isinstance(linkedin_value, str) and linkedin_value.strip():
        normalized["linkedin"] = _extract_linkedin_slug(linkedin_value)
    return normalized


def escape_tex(text: str) -> str:
    text = _preprocess_unicode(str(text))
    substitutions = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "#": r"\#",
        "%": r"\%",
        "&": r"\&",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in substitutions.items():
        text = text.replace(old, new)
    return _restore_unicode_tokens(text)


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _apply_basic_markdown(text: str) -> str:
    text = _preprocess_unicode(text)
    text = escape_tex(text)
    text = _restore_unicode_tokens(text)
    text = text.replace("**", "__BOLD__")
    parts: list[str] = []
    bold = False
    for chunk in text.split("__BOLD__"):
        if bold:
            parts.append(r"\textbf{" + chunk + "}")
        else:
            parts.append(chunk)
        bold = not bold
    text = "".join(parts)
    text = text.replace("*", "__ITAL__")
    parts.clear()
    italic = False
    for chunk in text.split("__ITAL__"):
        if italic:
            parts.append(r"\textit{" + chunk + "}")
        else:
            parts.append(chunk)
        italic = not italic
    return "".join(parts)


def markdown_inline_to_latex(text: str) -> str:
    text = str(text).replace("\r\n", "\n").replace("\n", " ")
    if not text:
        return ""

    parts: list[str] = []
    last_end = 0
    for match in _LINK_PATTERN.finditer(text):
        if match.start() > last_end:
            parts.append(_apply_basic_markdown(text[last_end : match.start()]))
        label = match.group(1)
        url = match.group(2)
        label_latex = _apply_basic_markdown(label)
        url_latex = escape_tex(url)
        parts.append(r"\href{" + url_latex + r"}{" + label_latex + "}")
        last_end = match.end()

    if last_end < len(text):
        parts.append(_apply_basic_markdown(text[last_end:]))

    # If no links found, the above loop won't modify parts; handle plain text
    if not parts:
        return _apply_basic_markdown(text)
    return "".join(parts)


def create_latex_jinja_env() -> Environment:
    """
    Create a Jinja2 environment optimized for LaTeX templates.

    Key features:
    - Custom delimiters to avoid conflicts with LaTeX syntax
    - Disabled autoescape (LaTeX has its own escaping rules)
    - Optimized whitespace handling for clean output

    Returns:
        Configured Jinja2 Environment instance
    """
    env = Environment(
        loader=FileSystemLoader(LATEX_TEMPLATE_DIR),
        autoescape=False,  # LaTeX has its own escaping rules
        # Custom delimiters - completely avoid LaTeX syntax conflicts
        variable_start_string="(((",
        variable_end_string=")))",
        block_start_string="((*",
        block_end_string="*))",
        comment_start_string="((#",
        comment_end_string="#))",
        # Output format optimization
        trim_blocks=True,  # Remove first newline after block
        lstrip_blocks=True,  # Strip leading spaces before blocks
        keep_trailing_newline=True,  # Keep final newline in template
    )

    # Register custom filters for LaTeX
    env.filters["escape_tex"] = escape_tex
    env.filters["markdown_to_latex"] = markdown_inline_to_latex

    return env


# Create global Jinja2 environment (module-level singleton)
jinja_env = create_latex_jinja_env()


def render_section_with_template(section: dict[str, Any]) -> str:
    """
    Render a section using Jinja2 templates.

    This is the new unified rendering function that replaces the legacy
    render_summary(), render_skills(), render_experience(), etc.

    Args:
        section: Section data dictionary containing:
            - type: Section type (e.g., 'summary', 'experience', 'skills')
            - title: Section title
            - Other fields specific to section type

    Returns:
        Rendered LaTeX string

    Raises:
        TemplateNotFound: If template doesn't exist (falls back to entries.tex.j2)
    """
    section_type = section.get("type", "raw")
    section_type = section_type_normalize_str(section_type)
    template_name = f"sections/{section_type}.tex.j2"

    try:
        template = jinja_env.get_template(template_name)
        return template.render(section)
    except TemplateNotFound:
        # Fallback to generic entries template
        logger.warning(
            f"Template {template_name} not found, using fallback entries.tex.j2"
        )
        template = jinja_env.get_template("sections/entries.tex.j2")
        return template.render(section)


# ============================================================================
# Legacy Rendering Functions (kept for backward compatibility and backup)
# ============================================================================


def render_summary(section: dict[str, Any]) -> str:
    title = section.get("title", "Summary")
    bullets = section.get("bullets", [])
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cvitems}"]
    for bullet in bullets:
        lines.append("  \\item {" + markdown_inline_to_latex(bullet) + "}")
    lines.append("\\end{cvitems}")
    return "\n".join(lines) + "\n"


def render_skills(section: dict[str, Any]) -> str:
    title = section.get("title", "Skills")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cvskills}"]
    for group in section.get("groups", []):
        category = escape_tex(group.get("category", "Skills"))
        items = ", ".join(escape_tex(item) for item in group.get("items", []))
        lines.append("  \\cvskill\n    {" + category + "}\n    {" + items + "}")
    lines.append("\\end{cvskills}")
    return "\n".join(lines) + "\n"


def render_entries(section: dict[str, Any]) -> str:
    title = section.get("title", "Experience")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        role = escape_tex(entry.get("title", "Role"))
        organization = markdown_inline_to_latex(
            entry.get("organization", "Organization")
        )
        location = escape_tex(entry.get("location", ""))
        period = escape_tex(entry.get("period", ""))
        bullet_lines = []
        for bullet in entry.get("bullets", []):
            bullet_lines.append(
                "        \\item {" + markdown_inline_to_latex(bullet) + "}"
            )
        if bullet_lines:
            items = "\n".join(
                ["      \\begin{cvitems}"] + bullet_lines + ["      \\end{cvitems}"]
            )
        else:
            items = ""
        block = f"  \\cventry\n    {{{role}}}\n    {{{organization}}}\n    {{{location}}}\n    {{{period}}}\n    {{\n{items}\n    }}"
        lines.append(block)
    lines.append("\\end{cventries}")
    return "\n".join(lines) + "\n"


def render_experience(section: dict[str, Any]) -> str:
    """Render work experience section."""
    title = section.get("title", "Experience")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        position = escape_tex(entry.get("title", "Position"))
        company = markdown_inline_to_latex(entry.get("organization", "Company"))
        location = escape_tex(entry.get("location", ""))
        period = escape_tex(entry.get("period", ""))
        bullet_lines = []
        for bullet in entry.get("bullets", []):
            bullet_lines.append(
                "        \\item {" + markdown_inline_to_latex(bullet) + "}"
            )
        if bullet_lines:
            items = "\n".join(
                ["      \\begin{cvitems}"] + bullet_lines + ["      \\end{cvitems}"]
            )
        else:
            items = ""
        block = f"  \\cventry\n    {{{position}}}\n    {{{company}}}\n    {{{location}}}\n    {{{period}}}\n    {{\n{items}\n    }}"
        lines.append(block)
    lines.append("\\end{cventries}")
    return "\n".join(lines) + "\n"


def render_projects(section: dict[str, Any]) -> str:
    """Render projects section."""
    title = section.get("title", "Projects")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        project_name = escape_tex(entry.get("title", "Project"))
        context = markdown_inline_to_latex(entry.get("organization", ""))
        location = escape_tex(entry.get("location", ""))
        period = escape_tex(entry.get("period", ""))
        bullet_lines = []
        for bullet in entry.get("bullets", []):
            bullet_lines.append(
                "        \\item {" + markdown_inline_to_latex(bullet) + "}"
            )
        if bullet_lines:
            items = "\n".join(
                ["      \\begin{cvitems}"] + bullet_lines + ["      \\end{cvitems}"]
            )
        else:
            items = ""
        block = f"  \\cventry\n    {{{project_name}}}\n    {{{context}}}\n    {{{location}}}\n    {{{period}}}\n    {{\n{items}\n    }}"
        lines.append(block)
    lines.append("\\end{cventries}")
    return "\n".join(lines) + "\n"


def render_education(section: dict[str, Any]) -> str:
    """Render education section."""
    title = section.get("title", "Education")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        degree = escape_tex(entry.get("title", "Degree"))
        school = markdown_inline_to_latex(entry.get("organization", "Institution"))
        location = escape_tex(entry.get("location", ""))
        period = escape_tex(entry.get("period", ""))
        bullet_lines = []
        for bullet in entry.get("bullets", []):
            bullet_lines.append(
                "        \\item {" + markdown_inline_to_latex(bullet) + "}"
            )
        if bullet_lines:
            items = "\n".join(
                ["      \\begin{cvitems}"] + bullet_lines + ["      \\end{cvitems}"]
            )
        else:
            items = ""
        block = f"  \\cventry\n    {{{degree}}}\n    {{{school}}}\n    {{{location}}}\n    {{{period}}}\n    {{\n{items}\n    }}"
        lines.append(block)
    lines.append("\\end{cventries}")
    return "\n".join(lines) + "\n"


# New unified renderers using Jinja2 templates
SECTION_RENDERERS = {
    "summary": render_section_with_template,
    "skills": render_section_with_template,
    "experience": render_section_with_template,
    "projects": render_section_with_template,
    "education": render_section_with_template,
}

# Legacy renderers mapping (for backward compatibility testing)
LEGACY_RENDERERS = {
    "summary": render_summary,
    "skills": render_skills,
    "experience": render_experience,
    "projects": render_projects,
    "education": render_education,
}


def section_type_normalize_str(section_type: SectionType | str) -> str:
    """Normalize section type."""
    type_str = ""
    if isinstance(section_type, SectionType):
        type_str = section_type.value
    elif isinstance(section_type, str):
        type_str = section_type
    else:
        raise TypeError(f"Unknown section type: {section_type}")
    return type_str


def render_section(section: dict[str, Any]) -> str:
    section_type = section.get("type")
    section_type = section_type_normalize_str(section_type)

    renderer = SECTION_RENDERERS.get(section_type)
    if renderer:
        return renderer(section)
    title = escape_tex(section.get("title", section.get("id", "Section")))
    body = markdown_inline_to_latex(section.get("content", ""))
    return f"\\cvsection{{{title}}}\n{body}\n"


def render_resume_from_dict(resume_dict: dict, version: str = "resume") -> str:
    """Render a resume document (``metadata`` + ``sections``) to LaTeX."""
    if not isinstance(resume_dict, dict):
        raise ValueError(f"Expected dictionary, got {type(resume_dict).__name__}")
    for field in ("metadata", "sections"):
        if field not in resume_dict:
            raise ValueError(f"Resume dictionary must contain '{field}' field")

    metadata = _normalize_metadata(resume_dict.get("metadata") or {})
    sections = apply_layout(resume_dict.get("sections") or [], resume_dict.get("style"))
    sections_content = "\n".join(render_section(section) for section in sections)
    return jinja_env.get_template("resume_main.tex.j2").render(
        metadata=metadata, sections_content=sections_content, version=version
    )


def render_resume(version: str) -> str:
    """Render a stored resume version to a complete LaTeX document."""
    data = load_resume(version)
    data.setdefault("metadata", {})
    data.setdefault("sections", [])
    return render_resume_from_dict(data, version)


def compile_tex_remote(
    tex_path: Path,
    output_path: Path | None = None,
    api_base_url: str | None = None,
    timeout: float = 120.0,
) -> Path:
    """
    Compile LaTeX to PDF using the remote latex_compile_api service.

    This function sends the tex file and assets directly via HTTP multipart upload
    to the remote API, which compiles and returns the PDF immediately.

    Args:
        tex_path: Path to the .tex file to compile
        output_path: Path where to save the PDF (default: same as tex_path with .pdf extension)
        api_base_url: Override for API base URL (default: from env or docker-compose)
        timeout: Request timeout in seconds (default: 120.0)

    Returns:
        Path to the generated PDF file

    Raises:
        RuntimeError: If compilation fails
        requests.RequestException: If API communication fails
    """
    if api_base_url is None:
        api_base_url = os.getenv("LATEX_COMPILE_API_URL", DEFAULT_LATEX_COMPILE_API_URL)
    api_base_url = api_base_url.rstrip("/")

    # Determine output path
    if output_path is None:
        output_path = tex_path.with_suffix(".pdf")

    # Build files list for multipart upload
    files = []
    tex_dir = tex_path.parent

    # Iterate to find all files in the directory recursively
    for item in tex_dir.rglob("*"):
        if item.is_file():
            # Calculate relative path to preserve directory structure (e.g. fonts/foo.ttf)
            rel_path = item.relative_to(tex_dir).as_posix()

            # Read content
            content = item.read_bytes()

            # Add to files list: ('files', (filename, content))
            files.append(("files", (rel_path, content)))

    # Submit compile request via multipart upload
    compile_url = f"{api_base_url}/v1/compile"
    data = {"main": tex_path.name}

    try:
        response = requests.post(compile_url, files=files, data=data, timeout=timeout)
        response.raise_for_status()

        output_path.write_bytes(response.content)
        return output_path

    except requests.RequestException as e:
        logger.error(f"Remote compilation failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        raise RuntimeError(f"Remote compilation failed: {e}") from e
