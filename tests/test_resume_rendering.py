import pytest

from resume_platform.resume_renderer import (
    _normalize_metadata,
    escape_tex,
    markdown_inline_to_latex,
    render_resume,
    render_resume_from_dict,
)


def test_markdown_unicode_dash_and_times_conversion():
    latex = markdown_inline_to_latex("Achieved 2–3× faster inference")
    assert "--" in latex
    assert "$\\times$" in latex
    assert "\\textperiodcentered" in markdown_inline_to_latex("Mountain View · Remote")
    assert "\\textperiodcentered" in escape_tex("Mountain View · Remote")


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


def test_render_stored_resume_produces_full_document():
    latex = render_resume("resume")
    assert "\\documentclass" in latex
    assert "\\begin{document}" in latex and "\\end{document}" in latex
