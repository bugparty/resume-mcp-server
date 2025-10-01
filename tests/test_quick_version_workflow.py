import os
import unittest
from pathlib import Path

from myagent.settings import load_settings, get_settings
from myagent.filesystem import init_filesystems, get_resume_fs

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR"),
    summary_path=os.getenv("TEST_RESUME_SUMMARY_PATH"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

from myagent.resume_loader import (
    create_new_version,
    list_modules_in_version,
    load_resume_section,
    update_resume_section,
)


class TestQuickVersionWorkflow(unittest.TestCase):
    def test_create_and_update_version(self):
        version = "temp_resume_version"
        target_filename = f"{version}.yaml"
        resume_fs = get_resume_fs()
        
        # Clean up if exists
        if resume_fs.exists(target_filename):
            resume_fs.remove(target_filename)

        result = create_new_version(version)
        self.assertIn("[Success]", result)
        self.assertTrue(resume_fs.exists(target_filename))

        modules = list_modules_in_version(f"{version}.yaml")
        self.assertIn("summary", modules)

        section_output = load_resume_section(f"{version}/summary")
        _, markdown = section_output.split("\n\n", 1)
        self.assertIn("## Summary", markdown)

        updated = update_resume_section(f"{version}/summary:## Summary\n- Updated bullet")
        self.assertIn("[Success]", updated)

        # Clean up
        if resume_fs.exists(target_filename):
            resume_fs.remove(target_filename)


if __name__ == "__main__":
    unittest.main()
