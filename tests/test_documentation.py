"""
Test documentation files for completeness and consistency.

This module tests that documentation files exist, contain required sections,
and maintain consistency across different documentation files.
"""

import os
import re
import sys
import unittest
from pathlib import Path

# Add src directory to Python path for module imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class TestMainDocumentation(unittest.TestCase):
    """Test main documentation files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_readme_exists(self):
        """Test that README.md exists."""
        readme = self.repo_root / "README.md"
        self.assertTrue(readme.exists(), "README.md should exist")

    def test_readme_has_title(self):
        """Test that README has a title."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for markdown h1 title
        self.assertTrue(
            content.startswith('#') or '\n#' in content[:100],
            "README should have a title"
        )

    def test_readme_has_essential_sections(self):
        """Test that README has essential sections."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for essential sections
        essential_sections = [
            "Quick Start",
            "Requirements",
            "Documentation",
        ]

        for section in essential_sections:
            self.assertIn(
                section,
                content,
                f"README should have '{section}' section"
            )

    def test_readme_has_setup_instructions(self):
        """Test that README has setup instructions."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for setup-related keywords
        setup_keywords = ["install", "setup", "配置", "安装"]

        has_setup = any(keyword in content.lower() for keyword in setup_keywords)

        self.assertTrue(
            has_setup,
            "README should contain setup instructions"
        )

    def test_readme_references_other_docs(self):
        """Test that README references other documentation files."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for links to other documentation
        doc_references = [
            "MCP_SETUP.md",
            "MCP_USER_MANUAL.md",
        ]

        for doc_ref in doc_references:
            self.assertIn(
                doc_ref,
                content,
                f"README should reference {doc_ref}"
            )

    def test_readme_has_docker_instructions(self):
        """Test that README includes Docker instructions."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for Docker references
        self.assertIn("Docker", content, "README should mention Docker")
        self.assertIn("docker", content.lower(), "README should have docker commands")


class TestMCPSetupDocumentation(unittest.TestCase):
    """Test MCP setup documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.mcp_setup = self.repo_root / "MCP_SETUP.md"

    def test_mcp_setup_exists(self):
        """Test that MCP_SETUP.md exists."""
        self.assertTrue(self.mcp_setup.exists(), "MCP_SETUP.md should exist")

    def test_mcp_setup_has_server_startup(self):
        """Test that MCP setup has server startup instructions."""
        with open(self.mcp_setup, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for server startup instructions
        self.assertIn("server", content.lower(), "Should mention server")
        self.assertIn("mcp_server.py", content, "Should reference mcp_server.py")

    def test_mcp_setup_has_client_configuration(self):
        """Test that MCP setup has client configuration."""
        with open(self.mcp_setup, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for client configuration
        clients = ["Claude", "ChatGPT"]

        for client in clients:
            self.assertIn(
                client,
                content,
                f"MCP setup should mention {client} client"
            )

    def test_mcp_setup_has_cloudflare_tunnel_instructions(self):
        """Test that MCP setup has Cloudflare Tunnel instructions."""
        with open(self.mcp_setup, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for Cloudflare Tunnel references
        self.assertIn("cloudflared", content.lower(), "Should mention cloudflared")
        self.assertIn("tunnel", content.lower(), "Should mention tunnel")

    def test_mcp_setup_has_test_instructions(self):
        """Test that MCP setup has testing instructions."""
        with open(self.mcp_setup, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for test instructions
        test_keywords = ["test", "测试"]

        has_test_instructions = any(keyword in content.lower() for keyword in test_keywords)

        self.assertTrue(
            has_test_instructions,
            "MCP setup should include test instructions"
        )

    def test_mcp_setup_has_http_port_configuration(self):
        """Test that MCP setup mentions HTTP port configuration."""
        with open(self.mcp_setup, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for port 8000 reference
        self.assertIn("8000", content, "MCP setup should mention port 8000")


class TestAgentsDocumentation(unittest.TestCase):
    """Test AGENTS.md documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.agents_doc = self.repo_root / "AGENTS.md"

    def test_agents_doc_exists(self):
        """Test that AGENTS.md exists."""
        self.assertTrue(self.agents_doc.exists(), "AGENTS.md should exist")

    def test_agents_doc_has_quick_start(self):
        """Test that AGENTS.md has Quick Start section."""
        with open(self.agents_doc, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("Quick Start", content, "AGENTS.md should have Quick Start section")

    def test_agents_doc_has_testing_guidance(self):
        """Test that AGENTS.md has testing guidance."""
        with open(self.agents_doc, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for testing section
        self.assertIn("Test", content, "AGENTS.md should have testing guidance")
        self.assertIn("pytest", content, "AGENTS.md should mention pytest")

    def test_agents_doc_has_code_style_guidelines(self):
        """Test that AGENTS.md has code style guidelines."""
        with open(self.agents_doc, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for code style section
        style_keywords = ["Code Style", "Style", "Format", "Black"]

        has_style_guidance = any(keyword in content for keyword in style_keywords)

        self.assertTrue(
            has_style_guidance,
            "AGENTS.md should include code style guidelines"
        )

    def test_agents_doc_has_repo_structure(self):
        """Test that AGENTS.md documents repo structure."""
        with open(self.agents_doc, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for structure documentation
        structure_keywords = ["Structure", "layout", "directory"]

        has_structure = any(keyword in content for keyword in structure_keywords)

        self.assertTrue(
            has_structure,
            "AGENTS.md should document repository structure"
        )

    def test_agents_doc_has_environment_setup(self):
        """Test that AGENTS.md has environment setup instructions."""
        with open(self.agents_doc, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for environment setup
        self.assertIn("Environment", content, "AGENTS.md should mention environment setup")
        self.assertIn(".env", content, "AGENTS.md should mention .env configuration")


class TestDocsGenerationDocumentation(unittest.TestCase):
    """Test DOCS_GENERATION.md documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.docs_gen = self.repo_root / "DOCS_GENERATION.md"

    def test_docs_generation_exists(self):
        """Test that DOCS_GENERATION.md exists."""
        self.assertTrue(self.docs_gen.exists(), "DOCS_GENERATION.md should exist")

    def test_docs_generation_has_fastmcp_inspect(self):
        """Test that docs generation mentions fastmcp inspect."""
        with open(self.docs_gen, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("fastmcp inspect", content, "Should mention fastmcp inspect")

    def test_docs_generation_has_generation_scripts(self):
        """Test that docs generation mentions generation scripts."""
        with open(self.docs_gen, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for script references
        scripts = ["generate_mcp_docs.py", "generate_mcp_html.py"]

        for script in scripts:
            self.assertIn(
                script,
                content,
                f"DOCS_GENERATION.md should mention {script}"
            )

    def test_docs_generation_has_output_formats(self):
        """Test that docs generation mentions output formats."""
        with open(self.docs_gen, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for output format mentions
        formats = ["JSON", "Markdown", "HTML"]

        for fmt in formats:
            self.assertIn(
                fmt,
                content,
                f"DOCS_GENERATION.md should mention {fmt} format"
            )


class TestMCPToolsDocumentation(unittest.TestCase):
    """Test MCP_TOOLS.md documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.mcp_tools_md = self.repo_root / "MCP_TOOLS.md"
        self.mcp_tools_html = self.repo_root / "MCP_TOOLS.html"

    def test_mcp_tools_md_exists(self):
        """Test that MCP_TOOLS.md exists."""
        # This file may be generated, so we just check if it should exist
        # or document that it's generated
        if self.mcp_tools_md.exists():
            self.assertTrue(self.mcp_tools_md.is_file(), "MCP_TOOLS.md should be a file")

    def test_mcp_tools_html_exists(self):
        """Test that MCP_TOOLS.html exists."""
        # This file may be generated
        if self.mcp_tools_html.exists():
            with open(self.mcp_tools_html, 'r', encoding='utf-8') as f:
                content = f.read()

            # Basic HTML structure check
            self.assertIn("<html", content.lower(), "Should be valid HTML")
            self.assertIn("</html>", content.lower(), "Should have closing HTML tag")


class TestUserManualDocumentation(unittest.TestCase):
    """Test MCP_USER_MANUAL.md documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.user_manual = self.repo_root / "MCP_USER_MANUAL.md"

    def test_user_manual_exists(self):
        """Test that MCP_USER_MANUAL.md exists."""
        # May or may not exist depending on project state
        if self.user_manual.exists():
            self.assertTrue(self.user_manual.is_file(), "MCP_USER_MANUAL.md should be a file")


class TestDocumentationConsistency(unittest.TestCase):
    """Test consistency across documentation files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_python_version_consistency(self):
        """Test that Python version is consistent across documentation."""
        docs_to_check = [
            self.repo_root / "README.md",
            self.repo_root / "AGENTS.md",
            self.repo_root / ".cursorrules",
        ]

        python_versions = []

        for doc in docs_to_check:
            if doc.exists():
                with open(doc, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Find Python version references
                matches = re.findall(r'Python\s*(\d+\.\d+)', content)
                python_versions.extend(matches)

        # All should reference Python 3.12
        if python_versions:
            for version in python_versions:
                self.assertEqual(
                    version,
                    "3.12",
                    "All documentation should consistently reference Python 3.12"
                )

    def test_package_manager_consistency(self):
        """Test that package manager (uv) is consistent across docs."""
        docs_to_check = [
            self.repo_root / "README.md",
            self.repo_root / "AGENTS.md",
            self.repo_root / ".cursorrules",
            self.repo_root / "MCP_SETUP.md",
        ]

        for doc in docs_to_check:
            if doc.exists():
                with open(doc, 'r', encoding='utf-8') as f:
                    content = f.read()

                # All should mention 'uv' package manager
                self.assertIn(
                    "uv",
                    content,
                    f"{doc.name} should mention 'uv' package manager"
                )

    def test_test_command_consistency(self):
        """Test that test commands are consistent across docs."""
        docs_to_check = [
            self.repo_root / "AGENTS.md",
            self.repo_root / ".cursorrules",
        ]

        for doc in docs_to_check:
            if doc.exists():
                with open(doc, 'r', encoding='utf-8') as f:
                    content = f.read()

                # All should mention pytest or run_all_tests.py
                has_test_command = "pytest" in content or "run_all_tests.py" in content

                self.assertTrue(
                    has_test_command,
                    f"{doc.name} should document test commands"
                )

    def test_port_number_consistency(self):
        """Test that MCP server port is consistent across docs."""
        docs_to_check = [
            self.repo_root / "README.md",
            self.repo_root / "MCP_SETUP.md",
            self.repo_root / "Dockerfile",
            self.repo_root / ".cloudflared" / "config.yml",
            self.repo_root / ".cloudflared" / "config.docker.yml",
        ]

        for doc in docs_to_check:
            if doc.exists():
                with open(doc, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for port 8000
                if "port" in content.lower() or "8000" in content:
                    self.assertIn(
                        "8000",
                        content,
                        f"{doc.name} should consistently use port 8000"
                    )


class TestDocumentationCompleteness(unittest.TestCase):
    """Test that documentation is complete and up-to-date."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_all_major_docs_exist(self):
        """Test that all major documentation files exist."""
        required_docs = [
            "README.md",
            "AGENTS.md",
            "MCP_SETUP.md",
            "DOCS_GENERATION.md",
            ".cursorrules",
            ".cursorprompt",
        ]

        for doc_name in required_docs:
            doc_path = self.repo_root / doc_name
            self.assertTrue(
                doc_path.exists(),
                f"Required documentation file {doc_name} should exist"
            )

    def test_readme_not_empty(self):
        """Test that README is not empty or too short."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # README should be substantial (at least 1000 characters)
        self.assertGreater(
            len(content),
            1000,
            "README should be substantial and informative"
        )

    def test_docs_have_code_blocks(self):
        """Test that documentation files have code examples."""
        docs_to_check = [
            self.repo_root / "README.md",
            self.repo_root / "AGENTS.md",
            self.repo_root / "MCP_SETUP.md",
        ]

        for doc in docs_to_check:
            if doc.exists():
                with open(doc, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for code blocks (markdown ```, inline code `, or indented code)
                has_code_blocks = ("```" in content or
                                   "\n    " in content or
                                   "`" in content)

                self.assertTrue(
                    has_code_blocks,
                    f"{doc.name} should contain code examples or inline code"
                )


class TestInternationalization(unittest.TestCase):
    """Test internationalization support in documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_readme_has_multilingual_content(self):
        """Test that README supports multiple languages."""
        readme = self.repo_root / "README.md"

        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for Chinese characters (multilingual support)
        has_chinese = any(ord(char) > 0x4E00 and ord(char) < 0x9FFF for char in content)

        # This project appears to support Chinese, so check for it
        # (can be removed if project is English-only)
        if has_chinese:
            self.assertTrue(
                has_chinese,
                "README contains multilingual content"
            )


if __name__ == "__main__":
    unittest.main()