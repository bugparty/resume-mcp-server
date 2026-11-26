"""Render a resume version to LaTeX, and optionally compile it to PDF.

Examples:
    uv run python scripts/render_resume_cli.py resume --tex build/resume.tex
    uv run python scripts/render_resume_cli.py resume --pdf build/resume.pdf
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from resume_platform.infrastructure.bootstrap import bootstrap
from resume_platform.publishing import stage_latex_project
from resume_platform.resume_renderer import compile_tex_remote, render_resume


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Resume version name, e.g. 'resume'")
    parser.add_argument("--data-dir", help="Override the resume YAML directory")
    parser.add_argument("--tex", type=Path, help="Write the generated LaTeX here")
    parser.add_argument(
        "--pdf", type=Path, help="Compile via the remote service and write the PDF here"
    )
    args = parser.parse_args(argv)

    overrides = {"data_dir": args.data_dir} if args.data_dir else {}
    bootstrap(**overrides)
    latex = render_resume(args.version)

    if args.tex:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(latex, encoding="utf-8")
    if args.pdf:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = compile_tex_remote(stage_latex_project(latex, Path(tmp)))
            args.pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf_path, args.pdf)
        print(f"PDF written to {args.pdf}", file=sys.stderr)
    if not args.tex and not args.pdf:
        print(latex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
