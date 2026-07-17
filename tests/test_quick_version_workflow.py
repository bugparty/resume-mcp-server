import unittest

from resume_platform.infrastructure.filesystem import get_resume_fs

# Runtime (settings + filesystems) is bootstrapped once by the session-scoped
# autouse fixture in conftest.py; no per-module initialization needed.
from resume_platform.resume.views import list_modules_in_version, load_resume_section
from resume_platform.resume.editing import update_resume_section, create_new_version


class TestQuickVersionWorkflow(unittest.TestCase):
    def test_create_and_update_version(self):
        version = "temp_resume_version"
        target_filename = f"{version}.yaml"
        resume_fs = get_resume_fs()
        
        # Clean up if exists
        if resume_fs.exists(target_filename):
            resume_fs.remove(target_filename)

        create_new_version(version)
        self.assertTrue(resume_fs.exists(target_filename))

        modules = list_modules_in_version(f"{version}.yaml")
        self.assertIn("summary", modules)

        section_output = load_resume_section(f"{version}/summary")
        _, markdown = section_output.split("\n\n", 1)
        self.assertIn("## Summary", markdown)

        update_resume_section(f"{version}/summary:## Summary\n- Updated bullet")

        # Clean up
        if resume_fs.exists(target_filename):
            resume_fs.remove(target_filename)


if __name__ == "__main__":
    unittest.main()
