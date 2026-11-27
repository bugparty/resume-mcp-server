"""Domain-level tests for reading and editing resume content.

Each test runs against a private copy of the fixture data (see conftest.py).
"""

import unittest

from resume_platform.infrastructure.filesystem import get_resume_fs
from resume_platform.resume.editing import (
    delete_text,
    insert_text,
    replace_text,
    update_section,
)
from resume_platform.resume.layout import set_section_order
from resume_platform.resume.repository import SectionNotFoundError, list_versions
from resume_platform.resume.versions import create_version
from resume_platform.resume.views import read_resume_text, render_resume_markdown


class TestResumeOperations(unittest.TestCase):
    def test_list_and_render_resume(self):
        versions = list_versions()
        self.assertIn("resume", versions)

        rendered = render_resume_markdown("resume")
        self.assertIn("## Summary", rendered)

        section = read_resume_text("resume", "summary")
        self.assertIn("## Summary", section)

        instructions, original_markdown = section.split("\n\n", 1)

        updated_markdown = "## Summary\n- Tailored bullet"
        update_section("resume", "summary", updated_markdown)


class TestResumeOperationsE2E(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeOperationsE2E"

    def tearDown(self):
        pass

    def test_create_and_delete_version(self):
        resume_fs = get_resume_fs()
        create_version(self.version)
        self.assertTrue(resume_fs.exists(f"{self.version}.yaml"))
        # Clean up by removing the test version
        resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))


class TestResumeOperationsE2E2(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeOperationsE2E2"
        create_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))

    def test_wrong_section_id(self):
        with self.assertRaises(SectionNotFoundError) as ctx:
            update_section(self.version, "work experience", "## Work Experience")
        self.assertIn("Did you mean 'experience'?", str(ctx.exception))

    def test_load_complete_resume_respects_section_order(self):
        set_section_order(self.version, ["skills", "summary", "experience"])

        rendered = render_resume_markdown(self.version)
        self.assertIn("## Technical Skills", rendered)
        self.assertIn("## Summary", rendered)
        self.assertLess(
            rendered.find("## Technical Skills"), rendered.find("## Summary")
        )

    def test_create_and_delete_version(self):
        section = "experience"
        new_content = """## Work Experience 
**Software Engineer | NovaTech Solutions | 2020 - Present** 
- Designed and implemented microservices architecture that reduced system downtime by 30%. 
- Led a team of 4 engineers to deliver a high-traffic e-commerce platform handling 1M+ monthly users. 
- Optimized database queries, improving API response times by 45%. 
**Backend Developer | CloudSphere Inc. | 2017 - 2020** 
- Developed RESTful APIs supporting mobile and web applications. 
- Collaborated with DevOps team to implement CI/CD pipelines, reducing deployment times by 50%. 
- Conducted code reviews and mentored junior developers, fostering team growth."""

        update_section(self.version, section, new_content)


class TestResumeAddSkills(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeAddSkills"
        create_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))

    def test_add_skills(self):
        section = "skills"
        new_content = """## Skills
        - Programming: Python, JavaScript, Go
        - Cloud Platforms: AWS, GCP, Docker, Kubernetes
        - Tools & Practices: Git, Jenkins, Terraform, Agile/Scrum
        - Other: Data analysis, system design, mentoring"""
        update_section(self.version, section, new_content)

    def test_add_skills_with_bold_non_bullet_categories(self):
        section = "skills"
        new_content = """## Skills
**Programming**: Python, C++, Rust

**Systems & Software**: Linux, Docker, networking diagnostics

**Tools**: Multimeter, Oscilloscope"""
        update_section(self.version, section, new_content)

        rendered = read_resume_text(self.version, section)
        self.assertIn("- Programming: Python, C++, Rust", rendered)
        self.assertIn(
            "- Systems & Software: Linux, Docker, networking diagnostics", rendered
        )
        self.assertIn("- Tools: Multimeter, Oscilloscope", rendered)

    def test_add_experience_project(self):
        section = "experience"
        new_content = """## Experience
        ### Software Engineer | NovaTech Solutions | 2020 - Present | Beijing, China
        - Designed and implemented microservices architecture that reduced system downtime by 30%. 
        - Led a team of 4 engineers to deliver a high-traffic e-commerce platform handling 1M+ monthly users. 
        - Optimized database queries, improving API response times by 45%. 
        ### Backend Developer | CloudSphere Inc. | 2017 - 2020 | Beijing, China
        - Developed RESTful APIs supporting mobile and web applications. 
        - Collaborated with DevOps team to implement CI/CD pipelines, reducing deployment times by 50%. 
        - Conducted code reviews and mentored junior developers, fostering team growth."""

        result = update_section(self.version, section, new_content)
        self.assertIn("Software Engineer", result)
        self.assertIn("Backend Developer", result)
        self.assertIn("Conducted code reviews and mentored junior developers", result)

    def test_add_experience_with_inline_location_pipe_format(self):
        section = "experience"
        new_content = """## Experience
        ### Software Engineer | NovaTech Solutions (Beijing, China) | 2020 - Present
        - Designed and implemented microservices architecture that reduced system downtime by 30%.
        ### Backend Developer | CloudSphere Inc. (Shanghai, China) | 2017 - 2020
        - Developed RESTful APIs supporting mobile and web applications."""

        update_section(self.version, section, new_content)

        rendered = read_resume_text(self.version, section)
        self.assertIn("Software Engineer", rendered)
        self.assertIn("NovaTech Solutions", rendered)
        self.assertIn("Beijing, China", rendered)
        self.assertIn("2020 - Present", rendered)

    def test_add_projects(self):
        section = "projects"
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
        result = update_section(self.version, section, new_content)
        self.assertIn("Projects", result)
        self.assertIn("Intelligent Recommendation Engine Optimization", result)

    def test_add_education_pipe_format(self):
        section = "education"
        new_content = """## Education
        ### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA"""
        result = update_section(self.version, section, new_content)
        self.assertIn("Master of Science in Computer Science", result)
        self.assertIn("Stanford University", result)
        self.assertIn("2016 - 2018", result)
        self.assertIn("Palo Alto, CA", result)

        rendered = read_resume_text(self.version, section)
        self.assertIn(
            "### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            rendered,
        )

    def test_add_education_pipe_without_location(self):
        section = "education"
        new_content = """## Education
        ### Bachelor of Science in Computer Engineering | Stanford University | 2012 - 2016"""
        update_section(self.version, section, new_content)

        rendered = read_resume_text(self.version, section)
        self.assertIn(
            "### Bachelor of Science in Computer Engineering | Stanford University | 2012 - 2016",
            rendered,
        )

    def test_add_education_legacy_bold_format_still_supported(self):
        section = "education"
        new_content = """## Education
        **Master of Science in Computer Science**
        Stanford University | 2016 - 2018"""
        result = update_section(self.version, section, new_content)
        self.assertIn("Master of Science in Computer Science", result)
        self.assertIn("Stanford University", result)
        self.assertIn("2016 - 2018", result)

    def test_add_education_legacy_heading_format_still_supported(self):
        section = "education"
        new_content = """## Education
        ### Master of Science in Computer Science — Stanford University (Palo Alto, CA) | 2016 - 2018"""
        update_section(self.version, section, new_content)

        rendered = read_resume_text(self.version, section)
        self.assertIn(
            "### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            rendered,
        )


class TestResumeSectionValidation(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeSectionValidation"
        create_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        if resume_fs.exists(f"{self.version}.yaml"):
            resume_fs.remove(f"{self.version}.yaml")
        self.assertFalse(resume_fs.exists(f"{self.version}.yaml"))

    def test_experience_invalid_format_does_not_overwrite_section(self):
        section = "experience"
        before = read_resume_text(self.version, section)
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "## Experience\nThis is a long paragraph without supported entry headings.",
            )
        self.assertIn("Failed to parse updated content", str(ctx.exception))
        self.assertIn("The parsed section became empty", str(ctx.exception))
        after = read_resume_text(self.version, section)
        self.assertEqual(before, after)

    def test_projects_invalid_format_returns_hint(self):
        section = "projects"
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "## Projects\n### Wrong heading without dates\nThis line never becomes a bullet",
            )
        self.assertIn("The parsed section became empty", str(ctx.exception))
        self.assertIn("Projects Section:", str(ctx.exception))

    def test_education_invalid_format_returns_error(self):
        section = "education"
        before = read_resume_text(self.version, section)
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "## Education\nUniversity of Somewhere only plain text without degree structure",
            )
        self.assertIn("The parsed section became empty", str(ctx.exception))
        self.assertIn(
            "### M.S. Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            str(ctx.exception),
        )
        after = read_resume_text(self.version, section)
        self.assertEqual(before, after)

    def test_skills_invalid_format_returns_error(self):
        section = "skills"
        before = read_resume_text(self.version, section)
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "## Skills\nThis paragraph ignores categories entirely and should be rejected.",
            )
        self.assertIn(
            "could not be parsed into valid categories/items", str(ctx.exception)
        )
        after = read_resume_text(self.version, section)
        self.assertEqual(before, after)

    def test_header_invalid_format_returns_example(self):
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                "header",
                "## Header\njust some words without colon pairs",
            )
        self.assertIn("key: value", str(ctx.exception))
        self.assertIn("email: john.doe@example.com", str(ctx.exception))

    def test_loader_comment_is_rejected(self):
        section = "summary"
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "<!-- Edit the markdown below. Preserve headings and bullet structure so we can parse updates reliably. -->\n\n## Summary\n- Focused bullet",
            )
        self.assertIn("loader instruction comment", str(ctx.exception))

    def test_multi_section_input_is_rejected(self):
        section = "summary"
        before = read_resume_text(self.version, section)
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "## Summary\n- Focused bullet\n\n## Skills\n- Python: FastAPI",
            )
        self.assertIn("only one section at a time", str(ctx.exception))
        after = read_resume_text(self.version, section)
        self.assertEqual(before, after)

    def test_title_mismatch_is_rejected(self):
        section = "experience"
        before = read_resume_text(self.version, section)
        with self.assertRaises(ValueError) as ctx:
            update_section(
                self.version,
                section,
                "## Skills\n- Programming: Python, Go",
            )
        self.assertIn("title/type may not match", str(ctx.exception))
        after = read_resume_text(self.version, section)
        self.assertEqual(before, after)

    def test_success_without_effective_change_mentions_it(self):
        section = "summary"
        section_output = read_resume_text(self.version, section)
        _, markdown = section_output.split("\n\n", 1)
        result = update_section(self.version, section, markdown)
        self.assertIn("No effective content change detected.", result)


class TestResumeTextEditing(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeTextEditing"
        create_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        if resume_fs.exists(f"{self.version}.yaml"):
            resume_fs.remove(f"{self.version}.yaml")

    def test_replace_resume_text_updates_single_section(self):
        replace_text(
            self.version,
            "Brief professional summary highlighting key experience and skills",
            "Updated professional summary highlighting platform engineering depth",
            section_id="summary",
        )
        rendered = read_resume_text(self.version, "summary")
        self.assertIn(
            "Updated professional summary highlighting platform engineering depth",
            rendered,
        )

    def test_update_resume_section_preserves_plain_single_and_double_quotes(self):
        update_section(
            self.version,
            "summary",
            '## Summary\n- He said "ship it" and it\'s done\n- Quote marker: \'single\' + "double"',
        )
        rendered = read_resume_text(self.version, "summary")
        self.assertIn('- He said "ship it" and it\'s done', rendered)
        self.assertIn("- Quote marker: 'single' + \"double\"", rendered)

    def test_replace_resume_text_handles_plain_quotes(self):
        replace_text(
            self.version,
            "Brief professional summary highlighting key experience and skills",
            'Quote-safe replacement: "platform" and it\'s reliable',
            section_id="summary",
        )
        rendered = read_resume_text(self.version, "summary")
        self.assertIn('Quote-safe replacement: "platform" and it\'s reliable', rendered)

    def test_insert_resume_text_after_anchor_updates_experience(self):
        insert_text(
            self.version,
            "\n- Improved p99 latency by 35% across critical APIs.",
            "after",
            "- Key responsibility or achievement",
            section_id="experience",
        )
        rendered = read_resume_text(self.version, "experience")
        self.assertIn("Improved p99 latency by 35%", rendered)

    def test_insert_resume_text_start_and_end_on_raw_section(self):
        insert_text(
            self.version, "- Top-of-section addition\n", "start", section_id="summary"
        )
        insert_text(
            self.version, "\n- End-of-section addition", "end", section_id="summary"
        )

        rendered = read_resume_text(self.version, "summary")
        self.assertIn("- Top-of-section addition", rendered)
        self.assertIn("- End-of-section addition", rendered)

    def test_delete_resume_text_removes_single_snippet(self):
        delete_text(
            self.version,
            "- Technologies: Technology 1, Technology 2, Technology 3",
            section_id="skills",
        )
        rendered = read_resume_text(self.version, "skills")
        self.assertNotIn(
            "- Technologies: Technology 1, Technology 2, Technology 3", rendered
        )

    def test_replace_resume_text_requires_match(self):
        before = read_resume_text(self.version, "summary")
        with self.assertRaises(ValueError) as ctx:
            replace_text(
                self.version,
                "this string does not exist",
                "replacement",
                section_id="summary",
            )
        self.assertIn("was not found", str(ctx.exception))
        after = read_resume_text(self.version, "summary")
        self.assertEqual(before, after)

    def test_delete_resume_text_rejects_ambiguous_match(self):
        before = read_resume_text(self.version, "summary")
        with self.assertRaises(ValueError) as ctx:
            delete_text(self.version, "bullet", section_id="summary")
        self.assertIn("matched", str(ctx.exception))
        after = read_resume_text(self.version, "summary")
        self.assertEqual(before, after)

    def test_read_resume_text_for_whole_resume_includes_header_and_sections(self):
        rendered = read_resume_text(self.version)
        self.assertIn("## Header", rendered)
        self.assertIn("## Summary", rendered)
        self.assertIn("## Experience", rendered)

    def test_replace_resume_text_updates_whole_resume_view(self):
        replace_text(self.version, "## Header", "## Header\nfirst_name: Taylor")
        whole = read_resume_text(self.version)
        self.assertIn("first_name: Taylor", whole)

    def test_whole_resume_edit_failure_does_not_write_partial_changes(self):
        before = read_resume_text(self.version)
        with self.assertRaises(ValueError) as ctx:
            replace_text(
                self.version,
                "## Experience\n### Job Title — Company Name (City, State) | Start Date - End Date\n- Key responsibility or achievement\n- Quantifiable result or impact\n- Technologies used or skills demonstrated\n\n### Previous Job Title — Previous Company (City, State) | Start Date - End Date\n- Major project or responsibility\n- Achievement with metrics\n- Technical skills applied",
                "## Experience\nThis paragraph breaks the parser for the whole section.",
            )
        self.assertIn("The parsed section became empty", str(ctx.exception))
        after = read_resume_text(self.version)
        self.assertEqual(before, after)

    def test_whole_resume_rejects_top_level_block_removal(self):
        before = read_resume_text(self.version)
        _, body = before.split("\n\n", 1)
        skills_start = body.index("\n\n## Technical Skills")
        skills_end = body.index("\n\n## Experience")
        skills_block = body[skills_start:skills_end]
        with self.assertRaises(ValueError) as ctx:
            delete_text(self.version, skills_block)
        self.assertIn("cannot add, remove, or reorder", str(ctx.exception))
        after = read_resume_text(self.version)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
