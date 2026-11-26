"""Version lifecycle (create/copy/delete), layout, and read-only views."""

from __future__ import annotations

import pytest

from resume_platform.resume import layout, repository, versions, views


def test_create_version_from_template() -> None:
    message = versions.create_version("fresh")
    assert "fresh" in message
    assert "fresh" in repository.list_versions()
    assert repository.load_resume("fresh") == repository.load_template()


def test_create_existing_version_fails() -> None:
    with pytest.raises(ValueError, match="already exists"):
        versions.create_version("resume")


def test_copy_version_duplicates_content() -> None:
    versions.copy_version("resume", "resume_copy")
    assert repository.load_resume("resume_copy") == repository.load_resume("resume")


@pytest.mark.parametrize(
    "source,target,error,match",
    [
        ("resume", "resume", ValueError, "must be different"),
        ("missing", "x", repository.ResumeNotFoundError, "missing"),
        ("resume", "resume_tesla_ml_performance_intern", ValueError, "already exists"),
    ],
)
def test_copy_version_errors(source, target, error, match) -> None:
    with pytest.raises(error, match=match):
        versions.copy_version(source, target)


def test_delete_version() -> None:
    versions.copy_version("resume", "temp")
    versions.delete_version("temp")
    assert "temp" not in repository.list_versions()


def test_base_version_cannot_be_deleted() -> None:
    with pytest.raises(ValueError, match="base resume version"):
        versions.delete_version("resume")


def test_delete_missing_version_fails() -> None:
    with pytest.raises(repository.ResumeNotFoundError):
        versions.delete_version("missing")


# --- layout -------------------------------------------------------------------


def test_layout_defaults_to_empty() -> None:
    assert layout.get_layout("resume") == {"section_order": [], "section_disabled": {}}


def test_hide_and_show_section() -> None:
    hidden = layout.set_section_visibility("resume", "summary", False)
    assert hidden["section_disabled"] == {"summary": True}
    assert "## Summary" not in views.render_resume_markdown("resume")

    shown = layout.set_section_visibility("resume", "summary", True)
    assert shown["section_disabled"] == {}
    assert "## Summary" in views.render_resume_markdown("resume")


def test_visibility_of_unknown_section_fails() -> None:
    with pytest.raises(repository.SectionNotFoundError):
        layout.set_section_visibility("resume", "nope", False)


def test_set_section_order_reports_skipped_ids() -> None:
    result = layout.set_section_order("resume", ["skills", "bogus", "summary"])
    assert result["section_order"] == ["skills", "summary"]
    assert result["skipped_ids"] == ["bogus"]
    rendered = views.render_resume_markdown("resume")
    assert rendered.index("## Skills") < rendered.index("## Summary")


def test_apply_layout_orders_then_appends_and_filters() -> None:
    sections = [{"id": i} for i in ("a", "b", "c", "d")]
    style = {"section_order": ["c", "a"], "section_disabled": {"b": True}}
    assert [s["id"] for s in layout.apply_layout(sections, style)] == ["c", "a", "d"]


# --- views --------------------------------------------------------------------


def test_list_sections_includes_header_and_hints() -> None:
    layout.set_section_visibility("resume", "education", False)
    sections = views.list_sections("resume")
    ids = [s["id"] for s in sections]
    assert ids[0] == "header"
    assert {"summary", "skills", "experience", "education"} <= set(ids)
    education = next(s for s in sections if s["id"] == "education")
    assert education["enabled"] is False
    assert all(s["format_hint"] for s in sections)


def test_read_resume_text_header_section() -> None:
    text = views.read_resume_text("resume", "header")
    assert text.startswith(views.FORMAT_INSTRUCTION_COMMENT)
    assert "## Header" in text
    assert "first_name:" in text


def test_render_resume_markdown_missing_version() -> None:
    with pytest.raises(repository.ResumeNotFoundError):
        views.render_resume_markdown("missing")
