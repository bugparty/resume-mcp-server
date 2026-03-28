import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient

# Add src directory to Python path for module imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from resume_platform.infrastructure.settings import load_settings
from resume_platform.infrastructure.filesystem import init_filesystems

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "test_data"

settings = load_settings(
    data_dir=os.getenv("TEST_RESUME_DATA_DIR") or (FIXTURE_ROOT / "resumes"),
    jd_dir=os.getenv("TEST_RESUME_JD_DIR") or (FIXTURE_ROOT / "jd"),
)

# Initialize filesystems for tests
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

from resume_platform.resume.views import (
    load_complete_resume,
    load_resume_section,
    read_resume_text,
)
from resume_platform.resume.editing import (
    update_resume_section,
    replace_resume_text,
    insert_resume_text,
    delete_resume_text,
    create_new_version,
)
from resume_platform.resume.repository import find_resume_versions, set_section_order
from resume_platform.infrastructure.filesystem import get_resume_fs


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
        update_resume_section("resume/summary", updated_markdown)

        # restore original content to keep fixture clean
        update_resume_section("resume/summary", original_markdown)


class TestResumeOperationsE2E(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeOperationsE2E"

    def tearDown(self):
        pass

    def test_create_and_delete_version(self):
        resume_fs = get_resume_fs()
        create_new_version(self.version)
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
        with self.assertRaises(KeyError) as ctx:
            update_resume_section(module_path, "## Work Experience")
        self.assertIn("did you mean 'experience'?", str(ctx.exception))

    def test_load_complete_resume_respects_section_order(self):
        set_section_order(self.version, ["skills", "summary", "experience"])

        rendered = load_complete_resume(f"{self.version}.yaml")
        self.assertIn("## Technical Skills", rendered)
        self.assertIn("## Summary", rendered)
        self.assertLess(
            rendered.find("## Technical Skills"), rendered.find("## Summary")
        )

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

        update_resume_section(module_path, new_content)


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
        update_resume_section(module_path, new_content)

    def test_add_skills_with_bold_non_bullet_categories(self):
        module_path = f"{self.version}/skills"
        new_content = """## Skills
**Programming**: Python, C++, Rust

**Systems & Software**: Linux, Docker, networking diagnostics

**Tools**: Multimeter, Oscilloscope"""
        update_resume_section(module_path, new_content)

        rendered = load_resume_section(module_path)
        self.assertIn("- Programming: Python, C++, Rust", rendered)
        self.assertIn(
            "- Systems & Software: Linux, Docker, networking diagnostics", rendered
        )
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

        update_resume_section(module_path, new_content)

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
        self.assertIn("Projects", result)
        self.assertIn("Intelligent Recommendation Engine Optimization", result)

    def test_add_education_pipe_format(self):
        module_path = f"{self.version}/education"
        new_content = """## Education
        ### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA"""
        result = update_resume_section(module_path, new_content)
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
        update_resume_section(module_path, new_content)

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
        self.assertIn("Master of Science in Computer Science", result)
        self.assertIn("Stanford University", result)
        self.assertIn("2016 - 2018", result)

    def test_add_education_legacy_heading_format_still_supported(self):
        module_path = f"{self.version}/education"
        new_content = """## Education
        ### Master of Science in Computer Science — Stanford University (Palo Alto, CA) | 2016 - 2018"""
        update_resume_section(module_path, new_content)

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
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "## Experience\nThis is a long paragraph without supported entry headings.",
            )
        self.assertIn("Failed to parse updated content", str(ctx.exception))
        self.assertIn("The parsed section became empty", str(ctx.exception))
        after = load_resume_section(module_path)
        self.assertEqual(before, after)

    def test_projects_invalid_format_returns_hint(self):
        module_path = f"{self.version}/projects"
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "## Projects\n### Wrong heading without dates\nThis line never becomes a bullet",
            )
        self.assertIn("The parsed section became empty", str(ctx.exception))
        self.assertIn("Projects Section:", str(ctx.exception))

    def test_education_invalid_format_returns_error(self):
        module_path = f"{self.version}/education"
        before = load_resume_section(module_path)
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "## Education\nUniversity of Somewhere only plain text without degree structure",
            )
        self.assertIn("The parsed section became empty", str(ctx.exception))
        self.assertIn(
            "### M.S. Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA",
            str(ctx.exception),
        )
        after = load_resume_section(module_path)
        self.assertEqual(before, after)

    def test_skills_invalid_format_returns_error(self):
        module_path = f"{self.version}/skills"
        before = load_resume_section(module_path)
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "## Skills\nThis paragraph ignores categories entirely and should be rejected.",
            )
        self.assertIn(
            "could not be parsed into valid categories/items", str(ctx.exception)
        )
        after = load_resume_section(module_path)
        self.assertEqual(before, after)

    def test_header_invalid_format_returns_example(self):
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                f"{self.version}/header",
                "## Header\njust some words without colon pairs",
            )
        self.assertIn("key: value", str(ctx.exception))
        self.assertIn("email: john.doe@example.com", str(ctx.exception))

    def test_loader_comment_is_rejected(self):
        module_path = f"{self.version}/summary"
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "<!-- Edit the markdown below. Preserve headings and bullet structure so we can parse updates reliably. -->\n\n## Summary\n- Focused bullet",
            )
        self.assertIn("loader instruction comment", str(ctx.exception))

    def test_multi_section_input_is_rejected(self):
        module_path = f"{self.version}/summary"
        before = load_resume_section(module_path)
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "## Summary\n- Focused bullet\n\n## Skills\n- Python: FastAPI",
            )
        self.assertIn("only one section at a time", str(ctx.exception))
        after = load_resume_section(module_path)
        self.assertEqual(before, after)

    def test_title_mismatch_is_rejected(self):
        module_path = f"{self.version}/experience"
        before = load_resume_section(module_path)
        with self.assertRaises(ValueError) as ctx:
            update_resume_section(
                module_path,
                "## Skills\n- Programming: Python, Go",
            )
        self.assertIn("title/type may not match", str(ctx.exception))
        after = load_resume_section(module_path)
        self.assertEqual(before, after)

    def test_success_without_effective_change_mentions_it(self):
        module_path = f"{self.version}/summary"
        section_output = load_resume_section(module_path)
        _, markdown = section_output.split("\n\n", 1)
        result = update_resume_section(module_path, markdown)
        self.assertIn("No effective content change detected.", result)


class TestResumeTextEditing(unittest.TestCase):
    def setUp(self):
        self.version = "TestResumeTextEditing"
        create_new_version(self.version)

    def tearDown(self):
        resume_fs = get_resume_fs()
        if resume_fs.exists(f"{self.version}.yaml"):
            resume_fs.remove(f"{self.version}.yaml")

    def test_read_resume_text_for_section_matches_existing_loader(self):
        self.assertEqual(
            read_resume_text(f"{self.version}/summary"),
            load_resume_section(f"{self.version}/summary"),
        )

    def test_replace_resume_text_updates_single_section(self):
        replace_resume_text(
            f"{self.version}/summary",
            "Brief professional summary highlighting key experience and skills",
            "Updated professional summary highlighting platform engineering depth",
        )
        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn(
            "Updated professional summary highlighting platform engineering depth",
            rendered,
        )

    def test_update_resume_section_preserves_plain_single_and_double_quotes(self):
        update_resume_section(
            f"{self.version}/summary",
            '## Summary\n- He said "ship it" and it\'s done\n- Quote marker: \'single\' + "double"',
        )
        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn('- He said "ship it" and it\'s done', rendered)
        self.assertIn('- Quote marker: \'single\' + "double"', rendered)

    def test_replace_resume_text_handles_plain_quotes(self):
        replace_resume_text(
            f"{self.version}/summary",
            "Brief professional summary highlighting key experience and skills",
            'Quote-safe replacement: "platform" and it\'s reliable',
        )
        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn('Quote-safe replacement: "platform" and it\'s reliable', rendered)

    def test_insert_resume_text_after_anchor_updates_experience(self):
        insert_resume_text(
            f"{self.version}/experience",
            "\n- Improved p99 latency by 35% across critical APIs.",
            "after",
            "- Key responsibility or achievement",
        )
        rendered = load_resume_section(f"{self.version}/experience")
        self.assertIn("Improved p99 latency by 35%", rendered)

    def test_insert_resume_text_start_and_end_on_raw_section(self):
        insert_resume_text(
            f"{self.version}/summary", "- Top-of-section addition\n", "start"
        )
        insert_resume_text(
            f"{self.version}/summary", "\n- End-of-section addition", "end"
        )

        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn("- Top-of-section addition", rendered)
        self.assertIn("- End-of-section addition", rendered)

    def test_delete_resume_text_removes_single_snippet(self):
        delete_resume_text(
            f"{self.version}/skills",
            "- Technologies: Technology 1, Technology 2, Technology 3",
        )
        rendered = load_resume_section(f"{self.version}/skills")
        self.assertNotIn(
            "- Technologies: Technology 1, Technology 2, Technology 3", rendered
        )

    def test_replace_resume_text_requires_match(self):
        before = load_resume_section(f"{self.version}/summary")
        with self.assertRaises(ValueError) as ctx:
            replace_resume_text(
                f"{self.version}/summary",
                "this string does not exist",
                "replacement",
            )
        self.assertIn("was not found", str(ctx.exception))
        after = load_resume_section(f"{self.version}/summary")
        self.assertEqual(before, after)

    def test_delete_resume_text_rejects_ambiguous_match(self):
        before = load_resume_section(f"{self.version}/summary")
        with self.assertRaises(ValueError) as ctx:
            delete_resume_text(f"{self.version}/summary", "bullet")
        self.assertIn("matched", str(ctx.exception))
        after = load_resume_section(f"{self.version}/summary")
        self.assertEqual(before, after)

    def test_read_resume_text_for_whole_resume_includes_header_and_sections(self):
        rendered = read_resume_text(self.version)
        self.assertIn("## Header", rendered)
        self.assertIn("## Summary", rendered)
        self.assertIn("## Experience", rendered)

    def test_replace_resume_text_updates_whole_resume_view(self):
        replace_resume_text(self.version, "## Header", "## Header\nfirst_name: Taylor")
        whole = read_resume_text(self.version)
        self.assertIn("first_name: Taylor", whole)

    def test_whole_resume_edit_failure_does_not_write_partial_changes(self):
        before = read_resume_text(self.version)
        with self.assertRaises(ValueError) as ctx:
            replace_resume_text(
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
            delete_resume_text(self.version, skills_block)
        self.assertIn("cannot add, remove, or reorder", str(ctx.exception))
        after = read_resume_text(self.version)
        self.assertEqual(before, after)

    def test_mcp_server_exposes_new_text_read_tool(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        mcp_server.init_filesystems(settings.resume_fs_url, settings.jd_fs_url)
        rendered = mcp_server.read_resume_text(self.version)
        self.assertIn("## Header", rendered)

    def test_mcp_server_update_resume_section_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        updated_markdown = "## Summary\n- Updated via MCP wrapper"
        result = mcp_server.update_resume_section(
            self.version, "summary", updated_markdown
        )

        self.assertIn(f"Updated {self.version}/summary", result)
        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn("Updated via MCP wrapper", rendered)

    def test_mcp_server_get_resume_section_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        rendered = mcp_server.get_resume_section(self.version, "summary")
        self.assertIn("## Summary", rendered)

    def test_mcp_server_load_complete_resume_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        rendered = mcp_server.load_complete_resume(self.version)
        self.assertIn("## Summary", rendered)
        self.assertIn("## Experience", rendered)

    def test_mcp_server_list_resume_versions_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        payload = mcp_server.list_resume_versions()
        data = json.loads(payload)
        self.assertIn("versions", data)
        self.assertIn("resume", data["versions"])

    def test_mcp_server_list_resume_sections_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        payload = mcp_server.list_resume_sections(self.version)
        self.assertIn("Available modules:", payload)
        self.assertIn("summary", payload)
        self.assertIn("experience", payload)

    def test_mcp_server_replace_resume_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        result = mcp_server.replace_resume_text(
            f"{self.version}/summary",
            "Brief professional summary highlighting key experience and skills",
            "Replaced via MCP wrapper",
        )
        self.assertIn(f"Updated {self.version}/summary", result)

        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn("Replaced via MCP wrapper", rendered)

    def test_mcp_server_insert_resume_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        result = mcp_server.insert_resume_text(
            f"{self.version}/summary",
            "\n- Inserted via MCP wrapper",
            "end",
        )
        self.assertIn(f"Updated {self.version}/summary", result)

        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn("Inserted via MCP wrapper", rendered)

    def test_mcp_server_read_resume_section_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        rendered = mcp_server.read_resume_section_text(self.version, "summary")
        self.assertIn("## Summary", rendered)

    def test_mcp_server_replace_resume_section_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        result = mcp_server.replace_resume_section_text(
            self.version,
            "summary",
            "Brief professional summary highlighting key experience and skills",
            "Replaced via explicit section wrapper",
        )
        self.assertIn(f"Updated {self.version}/summary", result)

        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn("Replaced via explicit section wrapper", rendered)

    def test_mcp_server_insert_resume_section_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        result = mcp_server.insert_resume_section_text(
            self.version,
            "summary",
            "\n- Inserted via explicit section wrapper",
            "end",
        )
        self.assertIn(f"Updated {self.version}/summary", result)

        rendered = load_resume_section(f"{self.version}/summary")
        self.assertIn("Inserted via explicit section wrapper", rendered)

    def test_mcp_server_delete_resume_section_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        result = mcp_server.delete_resume_section_text(
            self.version,
            "skills",
            "- Technologies: Technology 1, Technology 2, Technology 3",
        )
        self.assertIn(f"Updated {self.version}/skills", result)

        rendered = load_resume_section(f"{self.version}/skills")
        self.assertNotIn(
            "- Technologies: Technology 1, Technology 2, Technology 3", rendered
        )

    def test_mcp_server_delete_resume_text_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        result = mcp_server.delete_resume_text(
            f"{self.version}/skills",
            "- Technologies: Technology 1, Technology 2, Technology 3",
        )
        self.assertIn(f"Updated {self.version}/skills", result)

        rendered = load_resume_section(f"{self.version}/skills")
        self.assertNotIn(
            "- Technologies: Technology 1, Technology 2, Technology 3", rendered
        )

    def test_mcp_server_set_section_visibility_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        payload = mcp_server.set_section_visibility(self.version, "summary", False)
        data = json.loads(payload)
        self.assertEqual(data["version_name"], self.version)
        self.assertEqual(data["section_id"], "summary")
        self.assertFalse(data["enabled"])

        rendered = load_complete_resume(f"{self.version}.yaml")
        self.assertNotIn("## Summary", rendered)

    def test_mcp_server_set_section_order_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        payload = mcp_server.set_section_order(
            self.version, ["skills", "summary", "experience"]
        )
        data = json.loads(payload)
        self.assertEqual(data["version_name"], self.version)

        rendered = load_complete_resume(f"{self.version}.yaml")
        self.assertLess(
            rendered.find("## Technical Skills"), rendered.find("## Summary")
        )

    def test_mcp_server_get_section_style_wrapper(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        mcp_server.set_section_visibility(self.version, "summary", False)
        payload = mcp_server.get_section_style(self.version)
        data = json.loads(payload)
        self.assertEqual(data["version_name"], self.version)
        self.assertIn("style", data)
        self.assertIn("section_disabled", data["style"])
        self.assertIn("summary", data["style"]["section_disabled"])
        self.assertTrue(data["style"]["section_disabled"]["summary"])

    def test_mcp_server_http_app_exposes_streamable_and_sse_routes(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        app = mcp_server._build_dual_http_app()
        route_paths = {getattr(route, "path", None) for route in app.routes}

        self.assertIn("/mcp", route_paths)
        self.assertIn("/sse", route_paths)
        self.assertIn("/messages", route_paths)

    def test_mcp_server_http_app_adds_cors_headers(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        app = mcp_server._build_dual_http_app()
        client = TestClient(app)
        response = client.options(
            "/sse",
            headers={
                "Origin": "chrome-extension://kngiafgkdnlkgmefdafaibkibegkcaef",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")

    def test_mcp_server_list_data_directory_root(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        payload = mcp_server.list_data_directory("")
        data = json.loads(payload)

        self.assertEqual(data["path"], "")
        self.assertIn("items", data)
        self.assertIn("total_items", data)

    def test_mcp_server_records_exception_failure_event(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        with tempfile.TemporaryDirectory() as tmpdir:
            error_log_path = Path(tmpdir) / "mcp_error_events.jsonl"
            with patch.object(mcp_server, "mcp_error_events_file", error_log_path):

                @mcp_server.log_mcp_tool_call
                def _failing_tool(name: str, payload: dict[str, str]) -> str:
                    raise ValueError("boom")

                with self.assertRaises(ValueError):
                    _failing_tool("bad", {"a": "b"})

            self.assertTrue(error_log_path.exists())
            lines = error_log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

            event = json.loads(lines[0])
            self.assertEqual(event["failure_kind"], "exception")
            self.assertEqual(event["tool_name"], "_failing_tool")
            self.assertEqual(event["error_type"], "ValueError")
            self.assertEqual(event["error_message"], "boom")
            self.assertIn("event_id", event)
            self.assertIn("timestamp", event)
            self.assertIn("traceback", event)
            self.assertIsInstance(event["args"], list)
            self.assertIsInstance(event["kwargs"], dict)

    def test_mcp_server_records_error_response_failure_event(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        with tempfile.TemporaryDirectory() as tmpdir:
            error_log_path = Path(tmpdir) / "mcp_error_events.jsonl"
            with patch.object(mcp_server, "mcp_error_events_file", error_log_path):

                @mcp_server.log_mcp_tool_call
                def _error_response_tool() -> str:
                    return json.dumps({"error": "bad request", "code": 400})

                _error_response_tool()

            lines = error_log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

            event = json.loads(lines[0])
            self.assertEqual(event["failure_kind"], "error_response")
            self.assertEqual(event["tool_name"], "_error_response_tool")
            self.assertEqual(event["error_message"], "bad request")
            self.assertEqual(event["result_payload"]["code"], 400)
            self.assertIsNone(event["error_type"])
            self.assertIsNone(event["traceback"])

    def test_mcp_server_error_logs_route_empty_and_bad_params(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        with tempfile.TemporaryDirectory() as tmpdir:
            error_log_path = Path(tmpdir) / "mcp_error_events.jsonl"
            with patch.object(mcp_server, "mcp_error_events_file", error_log_path):
                app = mcp_server._build_dual_http_app()
                client = TestClient(app)

                response = client.get("/error-logs")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["total"], 0)
                self.assertEqual(body["items"], [])

                bad_limit = client.get("/error-logs?limit=0")
                self.assertEqual(bad_limit.status_code, 400)

                bad_offset = client.get("/error-logs?offset=-1")
                self.assertEqual(bad_offset.status_code, 400)

                bad_kind = client.get("/error-logs?failure_kind=bad")
                self.assertEqual(bad_kind.status_code, 400)

    def test_mcp_server_error_logs_route_filter_and_pagination(self):
        from resume_platform.interfaces.mcp import server as mcp_server

        events = [
            {
                "event_id": "1",
                "timestamp": "2026-03-28T10:00:00+00:00",
                "tool_name": "tool_a",
                "failure_kind": "exception",
                "args": [],
                "kwargs": {},
                "execution_time_ms": 10,
                "error_type": "ValueError",
                "error_message": "err-a",
                "traceback": "tb",
            },
            {
                "event_id": "2",
                "timestamp": "2026-03-28T11:00:00+00:00",
                "tool_name": "tool_b",
                "failure_kind": "error_response",
                "args": [],
                "kwargs": {},
                "execution_time_ms": 20,
                "error_type": None,
                "error_message": "err-b",
                "traceback": None,
            },
            {
                "event_id": "3",
                "timestamp": "2026-03-28T12:00:00+00:00",
                "tool_name": "tool_a",
                "failure_kind": "exception",
                "args": [],
                "kwargs": {},
                "execution_time_ms": 30,
                "error_type": "RuntimeError",
                "error_message": "err-c",
                "traceback": "tb",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            error_log_path = Path(tmpdir) / "mcp_error_events.jsonl"
            lines = [json.dumps(event, ensure_ascii=False) for event in events]
            lines.append("{bad json")
            error_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with patch.object(mcp_server, "mcp_error_events_file", error_log_path):
                app = mcp_server._build_dual_http_app()
                client = TestClient(app)

                response = client.get("/error-logs")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["total"], 3)
                self.assertEqual(body["items"][0]["event_id"], "3")
                self.assertEqual(body["parse_errors"], 1)

                filtered = client.get(
                    "/error-logs?tool_name=tool_a&failure_kind=exception&limit=1&offset=1"
                )
                self.assertEqual(filtered.status_code, 200)
                filtered_body = filtered.json()
                self.assertEqual(filtered_body["total"], 2)
                self.assertEqual(filtered_body["limit"], 1)
                self.assertEqual(filtered_body["offset"], 1)
                self.assertEqual(len(filtered_body["items"]), 1)
                self.assertEqual(filtered_body["items"][0]["event_id"], "1")


if __name__ == "__main__":
    unittest.main()
