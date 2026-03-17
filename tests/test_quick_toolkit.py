import os
import unittest
from pathlib import Path
from unittest.mock import patch

from resume_platform.infrastructure.settings import load_settings
from resume_platform.infrastructure.filesystem import init_filesystems

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "test_data"

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR") or (FIXTURE_ROOT / "resumes"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR") or (FIXTURE_ROOT / "jd"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

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
