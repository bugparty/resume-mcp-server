import os
import unittest
from pathlib import Path
from unittest.mock import patch

from myagent import resume_loader
from myagent.settings import load_settings
from myagent.filesystem import init_filesystems

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR"),
    summary_path=os.getenv("TEST_RESUME_SUMMARY_PATH"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

from myagent.resume_loader import (
    summarize_resumes_to_index,
    read_resume_summary,
    load_resume_section,
    tailor_section_for_jd,
)


class TestQuickToolkit(unittest.TestCase):
    def test_summary_and_tailor_workflow(self):
        result = summarize_resumes_to_index()
        self.assertIn("Summarized", result["message"])
        self.assertTrue(Path(result["yaml_path"]).exists())

        summary_content = read_resume_summary()["content"]
        self.assertIn("resume", summary_content)

        section_output = load_resume_section("resume/summary")
        _, markdown = section_output.split("\n\n", 1)

        fake_response = type("Response", (), {"content": "## Summary\n- Tailored bullet"})()

        class _FakeLLM:
            def invoke(self, *_args, **_kwargs):
                return fake_response

        with patch("myagent.resume_loader.llm", new=_FakeLLM()):
            tailored = tailor_section_for_jd("resume/summary", markdown, "JD Analysis")

        self.assertIn("Tailored bullet", tailored)


if __name__ == "__main__":
    unittest.main()
