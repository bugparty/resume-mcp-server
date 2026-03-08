import os
import sys
import unittest
from pathlib import Path

# Add src directory to Python path for module imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from myagent.settings import load_settings
from myagent.filesystem import init_filesystems

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "test_data"

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR") or (FIXTURE_ROOT / "resumes"),
    summary_path=os.getenv("TEST_RESUME_SUMMARY_PATH")
    or (FIXTURE_ROOT / "resume_summary.yaml"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR") or (FIXTURE_ROOT / "jd"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

from myagent.resume_loader import (
    find_resume_versions,
    load_complete_resume,
    load_resume_section,
    update_resume_section,
    summarize_resumes_to_index,
    read_resume_summary,
    create_new_version,
)
from myagent.filesystem import get_resume_fs


class TestResumeOperations(unittest.TestCase):
    def test_list_and_render_resume(self):
        versions = find_resume_versions()
        self.assertIn("resume", versions)

        rendered = load_complete_resume("resume.yaml")
        self.assertIn("## Summary", rendered)

        section = load_resume_section("resume/summary")
        self.assertIn("## Summary", section)

        instructions, original_markdown = section.split("\n\n", 1)

        updated_markdown = "## Summary\n- Tailored bullet"
        self.assertIn(
            "[Success]", update_resume_section("resume/summary", updated_markdown)
        )

        # restore original content to keep fixture clean
        self.assertIn(
            "[Success]", update_resume_section("resume/summary", original_markdown)
        )

    def test_summary_generation_and_read_yaml(self):
        result = summarize_resumes_to_index()
        self.assertTrue(Path(result["yaml_path"]).exists())

        content = read_resume_summary()["content"]
        self.assertIn("resumes:", content)


class TestResumeOperationsE2E(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeOperationsE2E"

    def tearDown(self):
        pass

    def test_create_and_delete_version(self):
        resume_fs = get_resume_fs()
        result = create_new_version(self.version)
        self.assertIn("[Success]", result)
        self.assertTrue(resume_fs.exists(f"{self.version}.yaml"))
        # Clean up by removing the test version
        resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))


class TestResumeOperationsE2E2(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeOperationsE2E2"
        create_new_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))

    def test_wrong_section_id(self):
        module_path = f"{self.version}/work experience"
        result = update_resume_section(module_path, "## Work Experience")
        self.assertIn("[Error]", result)
        self.assertIn("did you mean 'experience'?", result)

    def test_create_and_delete_version(self):
        module_path = f"{self.version}/experience"
        new_content = """## Work Experience 
**Software Engineer | NovaTech Solutions | 2020 - Present** 
- Designed and implemented microservices architecture that reduced system downtime by 30%. 
- Led a team of 4 engineers to deliver a high-traffic e-commerce platform handling 1M+ monthly users. 
- Optimized database queries, improving API response times by 45%. 
**Backend Developer | CloudSphere Inc. | 2017 - 2020** 
- Developed RESTful APIs supporting mobile and web applications. 
- Collaborated with DevOps team to implement CI/CD pipelines, reducing deployment times by 50%. 
- Conducted code reviews and mentored junior developers, fostering team growth."""

        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)


class TestResumeAddSkills(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeAddSkills"
        create_new_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))

    def test_add_skills(self):
        module_path = f"{self.version}/skills"
        new_content = """## Skills
        - Programming: Python, JavaScript, Go
        - Cloud Platforms: AWS, GCP, Docker, Kubernetes
        - Tools & Practices: Git, Jenkins, Terraform, Agile/Scrum
        - Other: Data analysis, system design, mentoring"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)

    def test_add_skills_with_bold_non_bullet_categories(self):
        module_path = f"{self.version}/skills"
        new_content = """## Skills
**Programming**: Python, C++, Rust

**Systems & Software**: Linux, Docker, networking diagnostics

**Tools**: Multimeter, Oscilloscope"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)

        rendered = load_resume_section(module_path)
        self.assertIn("- Programming: Python, C++, Rust", rendered)
        self.assertIn("- Systems & Software: Linux, Docker, networking diagnostics", rendered)
        self.assertIn("- Tools: Multimeter, Oscilloscope", rendered)

    def test_add_experience_project(self):
        module_path = f"{self.version}/experience"
        new_content = """## Experience
        ### Software Engineer | NovaTech Solutions | 2020 - Present | Beijing, China
        - Designed and implemented microservices architecture that reduced system downtime by 30%. 
        - Led a team of 4 engineers to deliver a high-traffic e-commerce platform handling 1M+ monthly users. 
        - Optimized database queries, improving API response times by 45%. 
        ### Backend Developer | CloudSphere Inc. | 2017 - 2020 | Beijing, China
        - Developed RESTful APIs supporting mobile and web applications. 
        - Collaborated with DevOps team to implement CI/CD pipelines, reducing deployment times by 50%. 
        - Conducted code reviews and mentored junior developers, fostering team growth."""

        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)
        self.assertIn("Software Engineer", result)
        self.assertIn("Backend Developer", result)
        self.assertIn("Conducted code reviews and mentored junior developers", result)

    def test_add_experience_with_inline_location_pipe_format(self):
        module_path = f"{self.version}/experience"
        new_content = """## Experience
        ### Software Engineer | NovaTech Solutions (Beijing, China) | 2020 - Present
        - Designed and implemented microservices architecture that reduced system downtime by 30%.
        ### Backend Developer | CloudSphere Inc. (Shanghai, China) | 2017 - 2020
        - Developed RESTful APIs supporting mobile and web applications."""

        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)

        rendered = load_resume_section(module_path)
        self.assertIn("Software Engineer", rendered)
        self.assertIn("NovaTech Solutions", rendered)
        self.assertIn("Beijing, China", rendered)
        self.assertIn("2020 - Present", rendered)

    def test_add_projects(self):
        module_path = f"{self.version}/projects"
        new_content = """## Projects
        ### Intelligent Recommendation Engine Optimization | 2021
        - Combined collaborative filtering with deep learning for personalized feeds.
        - Deployed in short-video app, increasing user retention by 12%.
        ### Distributed Log Analysis Platform | 2020
        - Built real-time streaming system using Flink & Kafka.
        - Enabled multi-scenario monitoring & alerting, reducing fault diagnosis time by 40%.
        ### IoT Data Middleware for Smart Home | 2023
        - Designed cross-platform data ingestion & cleansing workflows.
        - Built unified APIs (REST & GraphQL), improving developer adoption"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)

        # Verify projects section was updated correctly
        self.assertIn("Projects", result)
        self.assertIn("Intelligent Recommendation Engine Optimization", result)
    def test_add_education_pipe_format(self):
        module_path = f"{self.version}/education"
        new_content = """## Education
        ### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)
        self.assertIn("Master of Science in Computer Science", result)
        self.assertIn("Stanford University", result)
        self.assertIn("2016 - 2018", result)
        self.assertIn("Palo Alto, CA", result)

        rendered = load_resume_section(module_path)
        self.assertIn(
            "### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            rendered,
        )

    def test_add_education_pipe_without_location(self):
        module_path = f"{self.version}/education"
        new_content = """## Education
        ### Bachelor of Science in Computer Engineering | Stanford University | 2012 - 2016"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)

        rendered = load_resume_section(module_path)
        self.assertIn(
            "### Bachelor of Science in Computer Engineering | Stanford University | 2012 - 2016",
            rendered,
        )

    def test_add_education_legacy_bold_format_still_supported(self):
        module_path = f"{self.version}/education"
        new_content = """## Education
        **Master of Science in Computer Science**
        Stanford University | 2016 - 2018"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)
        self.assertIn("Master of Science in Computer Science", result)
        self.assertIn("Stanford University", result)
        self.assertIn("2016 - 2018", result)

    def test_add_education_legacy_heading_format_still_supported(self):
        module_path = f"{self.version}/education"
        new_content = """## Education
        ### Master of Science in Computer Science — Stanford University (Palo Alto, CA) | 2016 - 2018"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)

        rendered = load_resume_section(module_path)
        self.assertIn(
            "### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            rendered,
        )


class TestResumeSectionValidation(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeSectionValidation"
        create_new_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        if resume_fs.exists(f"{self.version}.yaml"):
            resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))

    def test_experience_invalid_format_does_not_overwrite_section(self):
        module_path = f"{self.version}/experience"
        before = load_resume_section(module_path)
        result = update_resume_section(
            module_path,
            "## Experience\nThis is a long paragraph without supported entry headings.",
        )
        after = load_resume_section(module_path)

        self.assertIn("[Error]", result)
        self.assertIn("Failed to parse updated content", result)
        self.assertIn("The parsed section became empty", result)
        self.assertEqual(before, after)

    def test_projects_invalid_format_returns_hint(self):
        module_path = f"{self.version}/projects"
        result = update_resume_section(
            module_path,
            "## Projects\n### Wrong heading without dates\nThis line never becomes a bullet",
        )

        self.assertIn("[Error]", result)
        self.assertIn("The parsed section became empty", result)
        self.assertIn("Projects Section:", result)

    def test_education_invalid_format_returns_error(self):
        module_path = f"{self.version}/education"
        before = load_resume_section(module_path)
        result = update_resume_section(
            module_path,
            "## Education\nUniversity of Somewhere only plain text without degree structure",
        )
        after = load_resume_section(module_path)

        self.assertIn("[Error]", result)
        self.assertIn("The parsed section became empty", result)
        self.assertIn(
            "### M.S. Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            result,
        )
        self.assertEqual(before, after)

    def test_skills_invalid_format_returns_error(self):
        module_path = f"{self.version}/skills"
        before = load_resume_section(module_path)
        result = update_resume_section(
            module_path,
            "## Skills\nThis paragraph ignores categories entirely and should be rejected.",
        )
        after = load_resume_section(module_path)

        self.assertIn("[Error]", result)
        self.assertIn("could not be parsed into valid categories/items", result)
        self.assertEqual(before, after)

    def test_header_invalid_format_returns_example(self):
        result = update_resume_section(
            f"{self.version}/header",
            "## Header\njust some words without colon pairs",
        )

        self.assertIn("[Error]", result)
        self.assertIn("key: value", result)
        self.assertIn("email: john.doe@example.com", result)

    def test_loader_comment_is_rejected(self):
        module_path = f"{self.version}/summary"
        result = update_resume_section(
            module_path,
            "<!-- Edit the markdown below. Preserve headings and bullet structure so we can parse updates reliably. -->\n\n## Summary\n- Focused bullet",
        )

        self.assertIn("[Error]", result)
        self.assertIn("loader instruction comment", result)

    def test_multi_section_input_is_rejected(self):
        module_path = f"{self.version}/summary"
        before = load_resume_section(module_path)
        result = update_resume_section(
            module_path,
            "## Summary\n- Focused bullet\n\n## Skills\n- Python: FastAPI",
        )
        after = load_resume_section(module_path)

        self.assertIn("[Error]", result)
        self.assertIn("only one section at a time", result)
        self.assertEqual(before, after)

    def test_title_mismatch_is_rejected(self):
        module_path = f"{self.version}/experience"
        before = load_resume_section(module_path)
        result = update_resume_section(
            module_path,
            "## Skills\n- Programming: Python, Go",
        )
        after = load_resume_section(module_path)

        self.assertIn("[Error]", result)
        self.assertIn("title/type may not match", result)
        self.assertEqual(before, after)

    def test_success_without_effective_change_mentions_it(self):
        module_path = f"{self.version}/summary"
        section_output = load_resume_section(module_path)
        _, markdown = section_output.split("\n\n", 1)
        result = update_resume_section(module_path, markdown)

        self.assertIn("[Success]", result)
        self.assertIn("No effective content change detected.", result)


if __name__ == "__main__":
    unittest.main()
