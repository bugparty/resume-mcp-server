"""Command-line interface to render resumes to LaTeX/PDF using myagent."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from myagent.settings import load_settings
from myagent.resume_renderer import render_resume, compile_tex
from myagent.filesystem import init_filesystems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Resume version without extension, e.g., 'resume'")
    parser.add_argument("--data-dir", help="Override resume YAML directory")
    parser.add_argument("--summary-path", dest="summary_path", help="Override resume summary YAML path")
    parser.add_argument("--aggregate-path", dest="summary_path", help=argparse.SUPPRESS)
    parser.add_argument("--jd-dir", help="Override JD directory")
    parser.add_argument("--tex", type=Path, help="Path to write generated LaTeX")
    parser.add_argument("--pdf", type=Path, help="Path to write compiled PDF (requires xelatex)")
    parser.add_argument("--compile", action="store_true", help="Compile to PDF using xelatex")
    args = parser.parse_args()

    settings = load_settings(data_dir=args.data_dir, summary_path=args.summary_path, aggregate_path=args.summary_path, jd_dir=args.jd_dir)
    init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

    latex = render_resume(args.version)

    if args.tex:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(latex, encoding="utf-8")

    pdf_path = None
    if args.compile or args.pdf:
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tex_path = tmp_path / "resume.tex"
            tex_path.write_text(latex, encoding="utf-8")

            template_root = ROOT / "templates"
            shutil.copy(template_root / "awesome-cv.cls", tmp_path)
            fonts_src = template_root / "fonts"
            if fonts_src.exists():
                shutil.copytree(fonts_src, tmp_path / "fonts")

            compile_tex(tex_path)
            pdf_path = tex_path.with_suffix(".pdf")

            if args.pdf:
                args.pdf.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(pdf_path, args.pdf)
            elif args.compile:
                default_pdf = Path.cwd() / f"{args.version}.pdf"
                shutil.copy(pdf_path, default_pdf)
                print(f"PDF written to {default_pdf}")

    if args.tex is None:
        print(latex)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
