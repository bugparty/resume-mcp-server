import os
import unittest

from myagent.settings import load_settings
from myagent.filesystem import init_filesystems

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR"),
    summary_path=os.getenv("TEST_RESUME_SUMMARY_PATH"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

from myagent.resume_loader import find_resume_versions, load_complete_resume, load_resume_section


class TestResumeBasics(unittest.TestCase):
    def test_listing(self):
        versions = find_resume_versions()
        self.assertGreaterEqual(len(versions), 1)
        self.assertIn("resume", versions)

    def test_load_resume_and_section(self):
        rendered = load_complete_resume("resume.yaml")
        self.assertIn("## Summary", rendered)

        section = load_resume_section("resume/education")
        self.assertIn("## Education", section)


if __name__ == "__main__":
    unittest.main()
