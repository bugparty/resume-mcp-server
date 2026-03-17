from __future__ import annotations

from resume_platform import tools


def test_get_resume_section_tool_uses_module_path(monkeypatch) -> None:
    captured: list[str] = []

    def fake_load_resume_section(module_path: str) -> str:
        captured.append(module_path)
        return "## Summary\n- bullet"

    monkeypatch.setattr(tools, "load_resume_section", fake_load_resume_section)

    result = tools.get_resume_section_tool("resume", "summary")

    assert result == "## Summary\n- bullet"
    assert captured == ["resume/summary"]
