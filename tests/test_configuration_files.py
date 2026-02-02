"""
Test configuration files for structure and validity.

This module tests that configuration files like cloudflared config,
devcontainer.json, .gitignore, and other configuration files are
properly structured and contain required fields.
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Add src directory to Python path for module imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class TestCloudflaredConfiguration(unittest.TestCase):
    """Test Cloudflared configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.cloudflared_dir = self.repo_root / ".cloudflared"

    def test_cloudflared_directory_exists(self):
        """Test that .cloudflared directory exists."""
        self.assertTrue(
            self.cloudflared_dir.exists(),
            ".cloudflared directory should exist"
        )
        self.assertTrue(
            self.cloudflared_dir.is_dir(),
            ".cloudflared should be a directory"
        )

    def test_cloudflared_credentials_json_structure(self):
        """Test that cloudflared credentials JSON has required fields."""
        creds_file = self.cloudflared_dir / "599718c3-ca5e-4347-8b65-2f80c1ef91cf.json"

        self.assertTrue(creds_file.exists(), "Credentials JSON should exist")

        with open(creds_file, 'r') as f:
            creds = json.load(f)

        # Check required fields
        required_fields = ["AccountTag", "TunnelSecret", "TunnelID"]
        for field in required_fields:
            self.assertIn(field, creds, f"Credentials should contain {field}")
            self.assertIsInstance(creds[field], str, f"{field} should be a string")
            self.assertTrue(creds[field], f"{field} should not be empty")

    def test_cloudflared_config_yml_structure(self):
        """Test that cloudflared config.yml has required structure."""
        config_file = self.cloudflared_dir / "config.yml"

        self.assertTrue(config_file.exists(), "config.yml should exist")

        with open(config_file, 'r') as f:
            content = f.read()

        # Check required fields
        self.assertIn("tunnel:", content, "Config should specify tunnel")
        self.assertIn("credentials-file:", content, "Config should specify credentials file")
        self.assertIn("ingress:", content, "Config should specify ingress rules")
        self.assertIn("hostname:", content, "Config should specify hostname")
        self.assertIn("service:", content, "Config should specify service")

    def test_cloudflared_docker_config_yml_structure(self):
        """Test that cloudflared config.docker.yml has required structure."""
        config_file = self.cloudflared_dir / "config.docker.yml"

        self.assertTrue(config_file.exists(), "config.docker.yml should exist")

        with open(config_file, 'r') as f:
            content = f.read()

        # Check required fields
        self.assertIn("tunnel:", content, "Docker config should specify tunnel")
        self.assertIn("credentials-file:", content, "Docker config should specify credentials file")
        self.assertIn("ingress:", content, "Docker config should specify ingress rules")

        # Docker config should reference devcontainer service
        self.assertIn("devcontainer", content, "Docker config should reference devcontainer service")

    def test_cloudflared_cert_pem_structure(self):
        """Test that cert.pem has proper structure."""
        cert_file = self.cloudflared_dir / "cert.pem"

        self.assertTrue(cert_file.exists(), "cert.pem should exist")

        with open(cert_file, 'r') as f:
            content = f.read()

        # Check PEM structure
        self.assertIn("-----BEGIN ARGO TUNNEL TOKEN-----", content, "Should have BEGIN marker")
        self.assertIn("-----END ARGO TUNNEL TOKEN-----", content, "Should have END marker")

        # Check base64 content exists between markers
        lines = content.strip().split('\n')
        self.assertGreaterEqual(len(lines), 3, "Should have at least BEGIN, content, and END lines")


class TestDevContainerConfiguration(unittest.TestCase):
    """Test devcontainer configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.devcontainer_dir = self.repo_root / ".devcontainer"

    def test_devcontainer_directory_exists(self):
        """Test that .devcontainer directory exists."""
        self.assertTrue(
            self.devcontainer_dir.exists(),
            ".devcontainer directory should exist"
        )

    def test_devcontainer_json_structure(self):
        """Test that devcontainer.json has required structure."""
        config_file = self.devcontainer_dir / "devcontainer.json"

        self.assertTrue(config_file.exists(), "devcontainer.json should exist")

        with open(config_file, 'r') as f:
            config = json.load(f)

        # Check required fields
        self.assertIn("name", config, "devcontainer.json should have name")
        self.assertIn("dockerComposeFile", config, "Should specify docker compose file")
        self.assertIn("service", config, "Should specify service name")
        self.assertIn("workspaceFolder", config, "Should specify workspace folder")

        # Check VSCode customizations
        if "customizations" in config:
            self.assertIn("vscode", config["customizations"], "Should have vscode customizations")
            if "extensions" in config["customizations"]["vscode"]:
                extensions = config["customizations"]["vscode"]["extensions"]
                self.assertIsInstance(extensions, list, "Extensions should be a list")

    def test_dockerfile_base_structure(self):
        """Test that Dockerfile.base has proper structure."""
        dockerfile = self.devcontainer_dir / "Dockerfile.base"

        self.assertTrue(dockerfile.exists(), "Dockerfile.base should exist")

        with open(dockerfile, 'r') as f:
            content = f.read()

        # Check essential Dockerfile elements
        self.assertIn("FROM ", content, "Dockerfile should have FROM instruction")
        self.assertIn("USER", content, "Dockerfile should set user")
        self.assertIn("WORKDIR", content, "Dockerfile should set working directory")

        # Check for TeX Live installation (specific to this project)
        self.assertIn("texlive", content.lower(), "Dockerfile should install TeX Live")

        # Check for Python environment
        self.assertIn("python", content.lower(), "Dockerfile should mention Python")


class TestGitConfiguration(unittest.TestCase):
    """Test git-related configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_gitignore_exists(self):
        """Test that .gitignore exists."""
        gitignore = self.repo_root / ".gitignore"
        self.assertTrue(gitignore.exists(), ".gitignore should exist")

    def test_gitignore_essential_patterns(self):
        """Test that .gitignore contains essential patterns."""
        gitignore = self.repo_root / ".gitignore"

        with open(gitignore, 'r') as f:
            content = f.read()

        # Check essential patterns
        essential_patterns = [
            "__pycache__",  # Python cache
            ".env",  # Environment variables
            "*.py[oc]",  # Python compiled files
            ".venv",  # Virtual environment
        ]

        for pattern in essential_patterns:
            self.assertIn(
                pattern,
                content,
                f".gitignore should contain pattern: {pattern}"
            )

    def test_gitignore_no_secrets(self):
        """Test that .gitignore excludes common secret files."""
        gitignore = self.repo_root / ".gitignore"

        with open(gitignore, 'r') as f:
            content = f.read()

        # Check that sensitive patterns are ignored
        self.assertIn(".env", content, "Should ignore .env files")


class TestVSCodeConfiguration(unittest.TestCase):
    """Test VSCode configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.vscode_dir = self.repo_root / ".vscode"

    def test_vscode_directory_exists(self):
        """Test that .vscode directory exists."""
        self.assertTrue(
            self.vscode_dir.exists(),
            ".vscode directory should exist"
        )

    def test_launch_json_structure(self):
        """Test that launch.json has proper structure."""
        launch_file = self.vscode_dir / "launch.json"

        self.assertTrue(launch_file.exists(), "launch.json should exist")

        # VSCode launch.json may contain comments (JSON with comments - JSONC)
        # Read and remove comments before parsing
        with open(launch_file, 'r') as f:
            content = f.read()

        # Remove single-line comments (//...)
        import re
        content_no_comments = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)

        try:
            config = json.loads(content_no_comments)
        except json.JSONDecodeError:
            # If still fails, just check that file has required text
            self.assertIn("version", content, "launch.json should have version")
            self.assertIn("configurations", content, "launch.json should have configurations")
            return

        # Check required fields
        self.assertIn("version", config, "launch.json should have version")
        self.assertIn("configurations", config, "launch.json should have configurations")
        self.assertIsInstance(config["configurations"], list, "configurations should be a list")

        # Check at least one configuration exists
        self.assertGreater(
            len(config["configurations"]),
            0,
            "Should have at least one debug configuration"
        )

        # Check first configuration structure
        if config["configurations"]:
            first_config = config["configurations"][0]
            required_fields = ["name", "type", "request"]
            for field in required_fields:
                self.assertIn(
                    field,
                    first_config,
                    f"Debug configuration should have {field}"
                )


class TestIdeaConfiguration(unittest.TestCase):
    """Test IntelliJ IDEA configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.idea_dir = self.repo_root / ".idea"

    def test_idea_directory_exists(self):
        """Test that .idea directory exists."""
        self.assertTrue(
            self.idea_dir.exists(),
            ".idea directory should exist"
        )

    def test_idea_gitignore_exists(self):
        """Test that .idea/.gitignore exists."""
        gitignore = self.idea_dir / ".gitignore"
        self.assertTrue(gitignore.exists(), ".idea/.gitignore should exist")

        with open(gitignore, 'r') as f:
            content = f.read()

        # Should ignore workspace-specific files
        self.assertIn("workspace.xml", content, "Should ignore workspace.xml")


class TestDockerConfiguration(unittest.TestCase):
    """Test Docker configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_dockerfile_exists(self):
        """Test that Dockerfile exists."""
        dockerfile = self.repo_root / "Dockerfile"
        self.assertTrue(dockerfile.exists(), "Dockerfile should exist")

    def test_dockerfile_structure(self):
        """Test that Dockerfile has proper structure."""
        dockerfile = self.repo_root / "Dockerfile"

        with open(dockerfile, 'r') as f:
            content = f.read()

        # Check essential Dockerfile instructions
        self.assertIn("FROM ", content, "Dockerfile should have FROM instruction")
        self.assertIn("WORKDIR", content, "Dockerfile should set working directory")
        self.assertIn("COPY", content, "Dockerfile should copy files")
        self.assertIn("EXPOSE", content, "Dockerfile should expose ports")

        # Check for specific project requirements
        self.assertIn("uv", content.lower(), "Dockerfile should mention uv package manager")
        self.assertIn("python", content.lower(), "Dockerfile should be based on Python")

        # Check for MCP server port
        self.assertIn("8000", content, "Dockerfile should expose port 8000 for MCP server")


class TestCursorConfiguration(unittest.TestCase):
    """Test Cursor IDE configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_cursorrules_exists(self):
        """Test that .cursorrules exists."""
        cursorrules = self.repo_root / ".cursorrules"
        self.assertTrue(cursorrules.exists(), ".cursorrules should exist")

    def test_cursorrules_content_structure(self):
        """Test that .cursorrules has proper content."""
        cursorrules = self.repo_root / ".cursorrules"

        with open(cursorrules, 'r') as f:
            content = f.read()

        # Check for essential sections
        self.assertIn("Project Structure", content, "Should have Project Structure section")
        self.assertIn("Python Environment", content, "Should have Python Environment section")
        self.assertIn("Testing", content, "Should have Testing section")

        # Check for important commands
        self.assertIn("uv", content, "Should mention uv package manager")
        self.assertIn("pytest", content, "Should mention pytest")

    def test_cursorprompt_exists(self):
        """Test that .cursorprompt exists."""
        cursorprompt = self.repo_root / ".cursorprompt"
        self.assertTrue(cursorprompt.exists(), ".cursorprompt should exist")

    def test_cursorprompt_content_structure(self):
        """Test that .cursorprompt has proper content."""
        cursorprompt = self.repo_root / ".cursorprompt"

        with open(cursorprompt, 'r') as f:
            content = f.read()

        # Check for essential sections
        self.assertIn("Essential Setup", content, "Should have Essential Setup section")
        self.assertIn("Python Environment", content, "Should mention Python environment")
        self.assertIn("Development Workflow", content, "Should have Development Workflow section")


class TestDataDirectoryStructure(unittest.TestCase):
    """Test data directory structure and documentation."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.data_dir = self.repo_root / "data"

    def test_data_directory_exists(self):
        """Test that data directory exists."""
        self.assertTrue(
            self.data_dir.exists(),
            "data directory should exist"
        )

    def test_resumes_directory_exists(self):
        """Test that data/resumes directory exists."""
        resumes_dir = self.data_dir / "resumes"
        self.assertTrue(
            resumes_dir.exists(),
            "data/resumes directory should exist"
        )

    def test_resumes_readme_exists(self):
        """Test that data/resumes/README.md exists."""
        readme = self.data_dir / "resumes" / "README.md"
        self.assertTrue(
            readme.exists(),
            "data/resumes/README.md should exist"
        )


class TestCloudflaredBinary(unittest.TestCase):
    """Test cloudflared binary configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_cloudflared_file_exists(self):
        """Test that cloudflared file exists (may be binary or script)."""
        cloudflared = self.repo_root / "cloudflared"
        # This file may or may not exist in all environments
        # So we just check if it exists, not fail if it doesn't
        if cloudflared.exists():
            # If it exists, it should be executable or a valid file
            self.assertTrue(
                cloudflared.is_file(),
                "cloudflared should be a file"
            )


class TestConfigurationConsistency(unittest.TestCase):
    """Test consistency across configuration files."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_cloudflared_configs_consistency(self):
        """Test that cloudflared configs reference same tunnel."""
        config_yml = self.repo_root / ".cloudflared" / "config.yml"
        config_docker_yml = self.repo_root / ".cloudflared" / "config.docker.yml"

        with open(config_yml, 'r') as f:
            config_content = f.read()

        with open(config_docker_yml, 'r') as f:
            docker_config_content = f.read()

        # Both should reference the same tunnel name
        self.assertIn("tunnel: resumemcp", config_content, "config.yml should specify tunnel")
        self.assertIn("tunnel: resumemcp", docker_config_content, "config.docker.yml should specify tunnel")

        # Both should reference the same credentials file
        creds_filename = "599718c3-ca5e-4347-8b65-2f80c1ef91cf.json"
        self.assertIn(creds_filename, config_content, "config.yml should reference credentials")
        self.assertIn(creds_filename, docker_config_content, "config.docker.yml should reference credentials")

    def test_hostname_consistency(self):
        """Test that hostname is consistent across configs."""
        config_yml = self.repo_root / ".cloudflared" / "config.yml"
        config_docker_yml = self.repo_root / ".cloudflared" / "config.docker.yml"

        with open(config_yml, 'r') as f:
            config_content = f.read()

        with open(config_docker_yml, 'r') as f:
            docker_config_content = f.read()

        # Both should use the same hostname
        hostname = "resumedev.0x1f0c.dev"
        self.assertIn(hostname, config_content, "config.yml should use consistent hostname")
        self.assertIn(hostname, docker_config_content, "config.docker.yml should use consistent hostname")


if __name__ == "__main__":
    unittest.main()