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
    def test_add_education(self):
        module_path = f"{self.version}/education"
        new_content = """ ## Education
        **Master of Science in Computer Science**
        Stanford University | 2016 - 2018"""
        result = update_resume_section(module_path, new_content)
        self.assertIn("[Success]", result)
        self.assertIn("Master of Science in Computer Science", result)
        self.assertIn("Stanford University", result)
        self.assertIn("2016 - 2018", result)
    

if __name__ == "__main__":
    unittest.main()
