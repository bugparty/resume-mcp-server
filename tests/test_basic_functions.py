import os
import unittest
from pathlib import Path

from resume_platform.infrastructure.settings import load_settings
from resume_platform.infrastructure.filesystem import init_filesystems

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "test_data"

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR") or (FIXTURE_ROOT / "resumes"),
    summary_path=os.getenv("TEST_RESUME_SUMMARY_PATH")
    or (FIXTURE_ROOT / "resume_summary.yaml"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR") or (FIXTURE_ROOT / "jd"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

from resume_platform.resume.views import load_complete_resume, load_resume_section
from resume_platform.resume.repository import find_resume_versions


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
