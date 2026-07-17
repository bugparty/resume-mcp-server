import unittest
from unittest.mock import patch

# Runtime (settings + filesystems) is bootstrapped once by the session-scoped
# autouse fixture in conftest.py; no per-module initialization needed.
from resume_platform.resume.views import load_resume_section
from resume_platform.resume.editing import tailor_section_for_jd


class TestQuickToolkit(unittest.TestCase):
    def test_tailor_workflow(self):
        section_output = load_resume_section("resume/summary")
        _, markdown = section_output.split("\n\n", 1)

        fake_response = type("Response", (), {"content": "## Summary\n- Tailored bullet"})()

        class _FakeLLM:
            def invoke(self, *_args, **_kwargs):
                return fake_response

        with patch("resume_platform.resume.editing.llm", new=_FakeLLM()):
            tailored = tailor_section_for_jd("resume/summary", markdown, "JD Analysis")

        self.assertIn("Tailored bullet", tailored)


if __name__ == "__main__":
    unittest.main()
