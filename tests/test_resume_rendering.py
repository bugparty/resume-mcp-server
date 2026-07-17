import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from resume_platform.infrastructure.filesystem import init_filesystems, reset_filesystems
from resume_platform.resume_renderer import (
    markdown_inline_to_latex,
    escape_tex,
    _normalize_metadata,
    render_resume_from_dict,
)
from resume_platform.tools import compile_resume_pdf_tool

# Runtime (settings + filesystems) is bootstrapped once by the session-scoped
# autouse fixture in conftest.py; no per-module initialization needed.


def test_markdown_unicode_dash_and_times_conversion():
    latex = markdown_inline_to_latex("Achieved 2–3× faster inference")
    assert "--" in latex
    assert "$\\times$" in latex
    assert "\\textperiodcentered" in markdown_inline_to_latex("Mountain View · Remote")
    assert "\\textperiodcentered" in escape_tex("Mountain View · Remote")


def test_compile_exports_latex_assets(monkeypatch, tmp_path, reset_runtime_after):
    # reset_runtime_after (conftest) restores the session filesystems on
    # teardown, so this test can freely repoint the globals at tmp dirs.
    reset_filesystems()

    resume_dir = tmp_path / "resumes"
    jd_dir = tmp_path / "jd"
    output_dir = tmp_path / "output"
    resume_dir.mkdir(parents=True, exist_ok=True)
    jd_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    init_filesystems(str(resume_dir), str(jd_dir), str(output_dir))

    def fake_compile(tex_path):
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4\n% fake\n")
        return pdf_path

    monkeypatch.setattr("resume_platform.tools.compile_tex_remote", fake_compile)

    tex_content = r"\documentclass{article}\begin{document}Hello\end{document}"
    result = compile_resume_pdf_tool(tex_content, "debug")

    assert result.latex_assets_dir is not None
    debug_dir_name = result.latex_assets_dir.rsplit("/", 1)[-1]
    debug_dir_path = output_dir / debug_dir_name
    assert debug_dir_path.exists()
    assert (debug_dir_path / "resume.tex").exists()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("bugparty", "bugparty"),
        ("github.com/bugparty", "bugparty"),
        ("https://github.com/bugparty", "bugparty"),
        ("https://github.com/bugparty/", "bugparty"),
        ("https://github.com/bugparty/awesome", "bugparty"),
        ("HTTP://github.com/BugParty", "BugParty"),
    ],
)
def test_normalize_metadata_github_handle(raw, expected):
    normalized = _normalize_metadata({"github": raw})
    assert normalized["github"] == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("bowmanhan", "bowmanhan"),
        ("linkedin.com/in/bowmanhan", "bowmanhan"),
        ("https://www.linkedin.com/in/bowmanhan", "bowmanhan"),
        ("https://linkedin.com/in/bowmanhan/", "bowmanhan"),
        ("https://linkedin.com/company/example", "example"),
        ("LINKEDIN.COM/in/BowManHan", "BowManHan"),
    ],
)
def test_normalize_metadata_linkedin_slug(raw, expected):
    normalized = _normalize_metadata({"linkedin": raw})
    assert normalized["linkedin"] == expected


def test_render_resume_respects_section_style_order_and_enabled():
    resume_dict = {
        "metadata": {"first_name": "Test", "last_name": "User"},
        "style": {
            "section_order": ["skills", "summary"],
            "section_disabled": {"education": True},
        },
        "sections": [
            {
                "type": "summary",
                "title": "Summary",
                "id": "summary",
                "bullets": ["First"],
            },
            {
                "type": "skills",
                "title": "Skills",
                "id": "skills",
                "groups": [{"category": "Languages", "items": ["Python"]}],
            },
            {
                "type": "entries",
                "title": "Education",
                "id": "education",
                "entries": [
                    {
                        "title": "B.S.",
                        "organization": "Uni",
                        "location": "",
                        "period": "",
                        "bullets": [],
                    }
                ],
            },
        ],
    }

    latex = render_resume_from_dict(resume_dict, version="styled")

    assert "Education" not in latex
    assert latex.find("Skills") != -1 and latex.find("Summary") != -1
    assert latex.find("Skills") < latex.find("Summary")
