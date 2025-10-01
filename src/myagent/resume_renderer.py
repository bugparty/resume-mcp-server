from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .resume_loader import load_complete_resume_as_dict


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
LEGACY_TEMPLATE = PROJECT_ROOT / "templates" / "resume_template.tex"
LATEX_TEMPLATE_DIR = PROJECT_ROOT / "templates" / "latex"

# Setup logging
logger = logging.getLogger(__name__)


def escape_tex(text: str) -> str:
    text = str(text)
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
    return text


def markdown_inline_to_latex(text: str) -> str:
    # Bold
    text = str(text).replace("\r\n", "\n").replace("\n", " ")
    text = escape_tex(text)
    text = text.replace("**", "__BOLD__")
    parts: List[str] = []
    bold = False
    for chunk in text.split("__BOLD__"):
        if bold:
            parts.append(r"\textbf{" + chunk + "}")
        else:
            parts.append(chunk)
        bold = not bold
    text = "".join(parts)
    # Italic
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


def render_section_with_template(section: Dict[str, any]) -> str:
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
    section_type = section.get("type", "entries")
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


def render_summary(section: Dict[str, any]) -> str:
    title = section.get("title", "Summary")
    bullets = section.get("bullets", [])
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cvitems}"]
    for bullet in bullets:
        lines.append("  \\item {" + markdown_inline_to_latex(bullet) + "}")
    lines.append("\\end{cvitems}")
    return "\n".join(lines) + "\n"


def render_skills(section: Dict[str, any]) -> str:
    title = section.get("title", "Skills")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cvskills}"]
    for group in section.get("groups", []):
        category = escape_tex(group.get("category", "Skills"))
        items = ", ".join(escape_tex(item) for item in group.get("items", []))
        lines.append("  \\cvskill\n    {" + category + "}\n    {" + items + "}")
    lines.append("\\end{cvskills}")
    return "\n".join(lines) + "\n"


def render_entries(section: Dict[str, any]) -> str:
    title = section.get("title", "Experience")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        role = escape_tex(entry.get("title", "Role"))
        organization = escape_tex(entry.get("organization", "Organization"))
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


def render_experience(section: Dict[str, any]) -> str:
    """Render work experience section."""
    title = section.get("title", "Experience")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        position = escape_tex(entry.get("title", "Position"))
        company = escape_tex(entry.get("organization", "Company"))
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


def render_projects(section: Dict[str, any]) -> str:
    """Render projects section."""
    title = section.get("title", "Projects")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        project_name = escape_tex(entry.get("title", "Project"))
        context = escape_tex(entry.get("organization", ""))
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


def render_education(section: Dict[str, any]) -> str:
    """Render education section."""
    title = section.get("title", "Education")
    lines = ["\\cvsection{" + escape_tex(title) + "}", "\\begin{cventries}"]
    for entry in section.get("entries", []):
        degree = escape_tex(entry.get("title", "Degree"))
        school = escape_tex(entry.get("organization", "Institution"))
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
    "entries": render_section_with_template,
    "experience": render_section_with_template,
    "projects": render_section_with_template,
    "education": render_section_with_template,
}

# Legacy renderers mapping (for backward compatibility testing)
LEGACY_RENDERERS = {
    "summary": render_summary,
    "skills": render_skills,
    "entries": render_entries,
    "experience": render_experience,
    "projects": render_projects,
    "education": render_education,
}


def render_section(section: Dict[str, any]) -> str:
    renderer = SECTION_RENDERERS.get(section.get("type"))
    if renderer:
        return renderer(section)
    title = escape_tex(section.get("title", section.get("id", "Section")))
    body = markdown_inline_to_latex(section.get("content", ""))
    return f"\\cvsection{{{title}}}\n{body}\n"


def resolve_template() -> str:
    """
    Legacy function: Load the old resume_template.tex.

    This is kept for backward compatibility.
    """
    # Fallback to legacy header if available, otherwise minimal template
    if LEGACY_TEMPLATE.exists():
        header = LEGACY_TEMPLATE.read_text(encoding="utf-8")
        # Strip input lines to avoid double-includes
        sanitized = []
        for line in header.splitlines():
            if line.strip().startswith("\\input"):
                continue
            sanitized.append(line)
        return "\n".join(sanitized)
    return r"""\documentclass[11pt, a4paper]{awesome-cv}
\begin{document}
"""


def render_resume_legacy(version: str, metadata: Dict, sections: List) -> str:
    """
    Legacy resume rendering using string replacement.

    This is the old implementation kept for backward compatibility.
    Uses templates/resume_template.tex with string replacement.

    Args:
        version: Resume version name
        metadata: Metadata dictionary
        sections: List of section dictionaries

    Returns:
        Complete LaTeX document as string
    """
    header = resolve_template()
    header_lines = [line for line in header.splitlines() if line.strip()]
    header_lines = [
        line for line in header_lines if line.strip() != "\\end{document}"
    ]

    # Replace metadata placeholders
    def replace_or_append(command: str, value: str) -> None:
        nonlocal header_lines
        pattern = f"\\{command}"
        found = False
        for idx, line in enumerate(header_lines):
            if line.strip().startswith(pattern):
                header_lines[idx] = f"\\{command}{{{value}}}"
                found = True
                break
        if not found:
            header_lines.insert(0, f"\\{command}{{{value}}}")

    first = escape_tex(metadata.get("first_name", ""))
    last = escape_tex(metadata.get("last_name", ""))
    if first or last:
        name_value = first
        if last:
            name_value += "}{" + last
        replace_or_append("name", name_value)
    position = escape_tex(metadata.get("position", ""))
    if position:
        replace_or_append("position", position)
    address = escape_tex(metadata.get("address", ""))
    if address:
        replace_or_append("address", address)
    mobile = escape_tex(metadata.get("mobile", ""))
    if mobile:
        replace_or_append("mobile", mobile)
    email = escape_tex(metadata.get("email", ""))
    if email:
        replace_or_append("email", email)
    github = escape_tex(metadata.get("github", ""))
    if github:
        replace_or_append("github", github)
    linkedin = escape_tex(metadata.get("linkedin", ""))
    if linkedin:
        replace_or_append("linkedin", linkedin)

    body = []
    in_document = False
    for line in header_lines:
        body.append(line)
        if line.strip() == "\\begin{document}":
            in_document = True
    if not in_document:
        body.append("\\begin{document}")
    body.extend(render_section(section) for section in sections)
    body.append("\\end{document}")
    return "\n".join(body) + "\n"


def render_resume(version: str) -> str:
    """
    Render a complete resume using Jinja2 templates.

    This function loads resume data from YAML and renders it to LaTeX
    using the main template (resume_main.tex.j2) and section templates.

    Args:
        version: Resume version name (YAML filename without extension)

    Returns:
        Complete LaTeX document as string

    Raises:
        ValueError: If data is not a dictionary
        TemplateNotFound: If main template is missing
    """
    data = load_complete_resume_as_dict(version)

    # Additional safety check in case the type annotation isn't enforced
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected dictionary from load_complete_resume_as_dict, got {type(data).__name__}"
        )

    # Get metadata and sections
    metadata = data.get("metadata", {})
    sections = data.get("sections", [])

    # Render all sections
    sections_content = "\n".join(render_section(section) for section in sections)

    # Render main template with metadata and sections
    try:
        main_template = jinja_env.get_template("resume_main.tex.j2")
        return main_template.render(
            metadata=metadata, sections_content=sections_content, version=version
        )
    except TemplateNotFound:
        # Fallback to legacy rendering if new template doesn't exist
        logger.warning(
            "Main template resume_main.tex.j2 not found, using legacy rendering"
        )
        return render_resume_legacy(version, metadata, sections)


def compile_tex(tex_path: Path) -> None:
    # Run xelatex in non-interactive mode to avoid blocking on errors
    subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_path.name,
        ],
        cwd=tex_path.parent,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render resume YAML into LaTeX and optionally PDF"
    )
    parser.add_argument("version", help="Resume version (YAML stem), e.g., 'resume'")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/output.tex"),
        help="Destination .tex file",
    )
    parser.add_argument(
        "--compile", action="store_true", help="Compile the generated TeX using xelatex"
    )
    args = parser.parse_args()

    tex = render_resume(args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(tex, encoding="utf-8")
    if args.compile:
        compile_tex(args.output)


if __name__ == "__main__":
    main()
