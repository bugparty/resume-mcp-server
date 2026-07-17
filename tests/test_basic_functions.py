import unittest

# Runtime (settings + filesystems) is bootstrapped once by the session-scoped
# autouse fixture in conftest.py; no per-module initialization needed.
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
