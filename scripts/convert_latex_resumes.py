"""Convert legacy awesome-cv LaTeX resumes into resume YAML versions.

uv run python scripts/convert_latex_resumes.py old/resume.tex [more.tex ...]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from resume_platform.paths import PROJECT_ROOT

OUTPUT_BASE = PROJECT_ROOT / "data" / "resumes"


class ParseError(RuntimeError):
    """Raised when LaTeX parsing fails."""


def strip_comments(text: str) -> str:
    """Remove LaTeX comments while keeping escaped percent signs."""

    cleaned_lines = []
    for line in text.splitlines():
        cleaned_lines.append(re.sub(r"(?<!\\)%.*$", "", line))
    return "\n".join(cleaned_lines)


def extract_braced(text: str, start: int) -> tuple[str, int]:
    """Extract the content inside a balanced brace pair starting at *start*."""

    if start >= len(text) or text[start] != "{":
        raise ParseError(f"Expected '{{' at position {start}")
    depth = 0
    buf: list[str] = []
    idx = start
    while idx < len(text):
        char = text[idx]
        if char == "{":
            depth += 1
            if depth > 1:
                buf.append(char)
        elif char == "}":
            depth -= 1
            if depth == 0:
                return "".join(buf), idx + 1
            buf.append(char)
        else:
            buf.append(char)
        idx += 1
    raise ParseError("Unbalanced braces in LaTeX content")


def latex_inline_to_markdown(text: str) -> str:
    """Convert a subset of LaTeX inline commands to Markdown equivalents."""

    text = text.replace("~", " ")
    result: list[str] = []
    idx = 0
    while idx < len(text):
        if text.startswith("\\textbf", idx):
            idx += len("\\textbf")
            while idx < len(text) and text[idx].isspace():
                idx += 1
            if idx < len(text) and text[idx] == "{":
                inner, idx = extract_braced(text, idx)
                result.append("**" + latex_inline_to_markdown(inner) + "**")
                continue
            result.append("\\textbf")
            continue
        if text.startswith("\\textit", idx):
            idx += len("\\textit")
            while idx < len(text) and text[idx].isspace():
                idx += 1
            if idx < len(text) and text[idx] == "{":
                inner, idx = extract_braced(text, idx)
                result.append("*" + latex_inline_to_markdown(inner) + "*")
                continue
            result.append("\\textit")
            continue
        if text.startswith("\\", idx):
            # Handle escaped symbols and line breaks
            if text.startswith("\\\\", idx):
                result.append("\n")
                idx += 2
                continue
            if text.startswith("\\enskip", idx):
                result.append(" ")
                idx += len("\\enskip")
                continue
            if text.startswith("\\cdotp", idx):
                result.append(" · ")
                idx += len("\\cdotp")
                continue
            if idx + 1 < len(text) and text[idx + 1] in "%&#$_{}":
                result.append(text[idx + 1])
                idx += 2
                continue
            # Skip solitary backslash
            idx += 1
            continue
        if text[idx] in "{}":
            idx += 1
            continue
        result.append(text[idx])
        idx += 1

    collapsed = re.sub(r"[ \t]+", " ", "".join(result))
    collapsed = re.sub(r"\s*\n\s*", "\n", collapsed)
    return collapsed.strip()


def read_command_args(text: str, command: str, count: int = 1) -> list[str]:
    pattern = re.compile(rf"\\{command}\b")
    match = pattern.search(text)
    if not match:
        return []
    args: list[str] = []
    idx = match.end()
    for _ in range(count):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text) or text[idx] != "{":
            return []
        arg, idx = extract_braced(text, idx)
        args.append(arg.strip())
    return args


def parse_cvitems(block: str) -> list[str]:
    """Parse cvitems block into a list of Markdown bullet strings."""

    block = strip_comments(block)
    items: list[str] = []
    idx = 0
    while idx < len(block):
        if block.startswith("\\item", idx):
            idx += len("\\item")
            while idx < len(block) and block[idx].isspace():
                idx += 1
            if idx < len(block) and block[idx] == "{":
                content, idx = extract_braced(block, idx)
                items.append(latex_inline_to_markdown(content))
                continue
        idx += 1
    return [item for item in (item.strip() for item in items) if item]


def parse_cventry_blocks(text: str) -> list[dict[str, Any]]:
    r"""Parse \cventry-like commands into structured dictionaries."""

    entries: list[dict[str, Any]] = []
    pattern = re.compile(r"\\cventry[^{]*")
    idx = 0
    while True:
        match = pattern.search(text, idx)
        if not match:
            break
        cursor = match.end()
        fields: list[str] = []
        for _ in range(5):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text) or text[cursor] != "{":
                raise ParseError("Malformed \\cventry block")
            content, cursor = extract_braced(text, cursor)
            fields.append(content.strip())
        bullets = parse_cvitems(fields[4]) if fields[4] else []
        entries.append(
            {
                "title": latex_inline_to_markdown(fields[0]),
                "organization": latex_inline_to_markdown(fields[1]),
                "location": latex_inline_to_markdown(fields[2]),
                "period": latex_inline_to_markdown(fields[3]),
                "bullets": bullets,
            }
        )
        idx = cursor
    return entries


def parse_cvparagraph(text: str) -> list[str]:
    """Extract paragraph lines from a cvparagraph environment."""

    match = re.search(
        r"\\begin\{cvparagraph\}(?P<body>[\s\S]*?)\\end\{cvparagraph\}", text
    )
    if not match:
        return []
    body = latex_inline_to_markdown(match.group("body"))
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return lines if lines else [body.strip()] if body.strip() else []


def parse_cvskills(text: str) -> list[dict[str, Any]]:
    """Parse cvskills block into category dictionaries."""

    entries: list[dict[str, Any]] = []
    pattern = re.compile(r"\\cvskill[^\s{]*")
    idx = 0
    while True:
        match = pattern.search(text, idx)
        if not match:
            break
        cursor = match.end()
        fields: list[str] = []
        for _ in range(2):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text) or text[cursor] != "{":
                raise ParseError("Malformed \\cvskill block")
            content, cursor = extract_braced(text, cursor)
            fields.append(content.strip())
        category = latex_inline_to_markdown(fields[0])
        items_raw = latex_inline_to_markdown(fields[1])
        items = [item.strip() for item in re.split(r",|;", items_raw) if item.strip()]
        entries.append({"category": category, "items": items})
        idx = cursor
    return entries


def convert_module(path: Path) -> dict[str, Any]:
    text = strip_comments(path.read_text(encoding="utf-8"))
    title_args = read_command_args(text, "cvsection", 1)
    title = latex_inline_to_markdown(title_args[0]) if title_args else None
    section: dict[str, Any]
    if "cvparagraph" in text:
        section = {"type": "summary", "bullets": parse_cvparagraph(text)}
    elif "cvskills" in text or "cvskillsII" in text:
        section = {"type": "skills", "groups": parse_cvskills(text)}
    elif "cventries" in text:
        section = {"type": "entries", "entries": parse_cventry_blocks(text)}
    else:
        section = {"type": "raw", "content": latex_inline_to_markdown(text)}
    if title:
        section["title"] = title
    return section


def convert_resume(main_tex: Path) -> dict[str, Any]:
    """Convert a main resume .tex entry point to structured data."""

    content = strip_comments(main_tex.read_text(encoding="utf-8"))
    metadata: dict[str, str] = {}
    name_args = read_command_args(content, "name", 2)
    if len(name_args) == 2:
        metadata["first_name"] = latex_inline_to_markdown(name_args[0])
        metadata["last_name"] = latex_inline_to_markdown(name_args[1])
    for key in ["position", "address", "mobile", "email", "github", "linkedin"]:
        args = read_command_args(content, key, 1)
        if args:
            metadata[key] = latex_inline_to_markdown(args[0])

    module_paths = re.findall(r"\\input\{([^}]*)\}", content)
    sections = []
    for module_path in module_paths:
        relative = module_path if module_path.endswith(".tex") else f"{module_path}.tex"
        module_file = main_tex.parent / relative
        if not module_file.exists():
            continue
        section_id = module_file.stem
        section = convert_module(module_file)
        section["id"] = section_id
        sections.append(section)

    return {
        "source": main_tex.name,
        "metadata": metadata,
        "sections": sections,
    }


def write_yaml(data: dict[str, Any], destination: Path) -> None:
    import yaml

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        nargs="+",
        type=Path,
        help="Main .tex file(s) of the resumes to convert",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_BASE,
        help="Target directory for YAML resumes",
    )
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    for tex_file in args.sources:
        data = convert_resume(tex_file)
        destination = args.output / f"{tex_file.stem}.yaml"
        write_yaml(data, destination)
        print(f"Converted {tex_file} -> {destination}")


if __name__ == "__main__":
    main()
