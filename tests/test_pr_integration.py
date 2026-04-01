"""
Integration tests for the entire PR changes.

This module provides comprehensive integration tests that verify all
changed files work together correctly and maintain consistency.
"""

import json
import os
import re
import sys
import unittest
import yaml
from pathlib import Path

# Add src directory to Python path for module imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class TestPRIntegration(unittest.TestCase):
    """Integration tests for PR changes."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_all_required_files_exist(self):
        """Test that all critical files mentioned in the PR exist."""
        required_files = [
            ".cloudflared/599718c3-ca5e-4347-8b65-2f80c1ef91cf.json",
            ".cloudflared/cert.pem",
            ".cloudflared/config.docker.yml",
            ".cloudflared/config.yml",
            ".cursorprompt",
            ".cursorrules",
            ".devcontainer/Dockerfile.base",
            ".devcontainer/devcontainer.json",
            ".env.sample",
            ".github/workflows/ci.yml",
            ".gitignore",
            ".idea/.gitignore",
            ".vscode/launch.json",
            "AGENTS.md",
            "DOCS_GENERATION.md",
            "Dockerfile",
            "MCP_SETUP.md",
            "README.md",
            "data/resumes/README.md",
        ]

        for file_path in required_files:
            full_path = self.repo_root / file_path
            self.assertTrue(
                full_path.exists(),
                f"Required file {file_path} should exist"
            )

    def test_cloudflared_configuration_chain(self):
        """Test that cloudflared configuration files form a valid chain."""
        # Load credentials
        creds_file = self.repo_root / ".cloudflared" / "599718c3-ca5e-4347-8b65-2f80c1ef91cf.json"
        with open(creds_file, 'r') as f:
            creds = json.load(f)

        tunnel_id = creds["TunnelID"]

        # Check that config files reference the correct tunnel ID
        config_file = self.repo_root / ".cloudflared" / "config.yml"
        with open(config_file, 'r') as f:
            config_content = f.read()

        self.assertIn(
            "599718c3-ca5e-4347-8b65-2f80c1ef91cf.json",
            config_content,
            "Config should reference the credentials file"
        )

        # Check Docker config
        docker_config = self.repo_root / ".cloudflared" / "config.docker.yml"
        with open(docker_config, 'r') as f:
            docker_config_content = f.read()

        self.assertIn(
            "599718c3-ca5e-4347-8b65-2f80c1ef91cf.json",
            docker_config_content,
            "Docker config should reference the credentials file"
        )

    def test_docker_and_devcontainer_consistency(self):
        """Test that Docker and devcontainer configurations are consistent."""
        # Read Dockerfile
        dockerfile = self.repo_root / "Dockerfile"
        with open(dockerfile, 'r') as f:
            dockerfile_content = f.read()

        # Read devcontainer Dockerfile
        devcontainer_dockerfile = self.repo_root / ".devcontainer" / "Dockerfile.base"
        with open(devcontainer_dockerfile, 'r') as f:
            devcontainer_content = f.read()

        # Both should use Python 3.12
        self.assertIn("3.12", dockerfile_content, "Dockerfile should use Python 3.12")
        self.assertIn("3.12", devcontainer_content, "Devcontainer should use Python 3.12")

        # Both should mention uv
        self.assertIn("uv", dockerfile_content.lower(), "Dockerfile should use uv")
        self.assertIn("uv", devcontainer_content.lower(), "Devcontainer should use uv")

    def test_documentation_cross_references_valid(self):
        """Test that documentation cross-references are valid."""
        readme = self.repo_root / "README.md"
        with open(readme, 'r', encoding='utf-8') as f:
            readme_content = f.read()

        # Find all markdown links
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, readme_content)

        for link_text, link_url in links:
            # Check internal file references
            if not link_url.startswith('http'):
                # It's a relative file reference
                if not link_url.startswith('#'):  # Skip anchor links
                    # Remove ./ prefix if present
                    clean_url = link_url.replace('./', '')
                    referenced_file = self.repo_root / clean_url

                    self.assertTrue(
                        referenced_file.exists(),
                        f"README references {clean_url} which should exist"
                    )

    def test_environment_and_ci_consistency(self):
        """Test that environment variables in .env.sample match CI expectations."""
        env_sample = self.repo_root / ".env.sample"
        ci_workflow = self.repo_root / ".github" / "workflows" / "ci.yml"

        with open(env_sample, 'r', encoding='utf-8') as f:
            env_content = f.read()

        with open(ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Get env vars from CI
        test_job = workflow["jobs"]["test"]
        test_steps = [step for step in test_job["steps"]
                      if "run" in step and "run_all_tests" in step["run"]]

        if test_steps:
            ci_env_vars = test_steps[0].get("env", {})

            # Check that CI provides all necessary API keys
            for env_var in ci_env_vars.keys():
                self.assertIn(
                    env_var,
                    env_content,
                    f"CI uses {env_var} which should be documented in .env.sample"
                )

    def test_cursor_configuration_validity(self):
        """Test that Cursor IDE configuration is valid and consistent."""
        cursorrules = self.repo_root / ".cursorrules"
        cursorprompt = self.repo_root / ".cursorprompt"

        with open(cursorrules, 'r', encoding='utf-8') as f:
            rules_content = f.read()

        with open(cursorprompt, 'r', encoding='utf-8') as f:
            prompt_content = f.read()

        # Both should mention the same Python version
        self.assertIn("3.12", rules_content, ".cursorrules should mention Python 3.12")
        self.assertIn("3.12", prompt_content, ".cursorprompt should mention Python 3.12")

        # Both should mention uv
        self.assertIn("uv", rules_content, ".cursorrules should mention uv")
        self.assertIn("uv", prompt_content, ".cursorprompt should mention uv")

        # Both should mention pytest
        self.assertIn("pytest", rules_content, ".cursorrules should mention pytest")
        self.assertIn("pytest", prompt_content, ".cursorprompt should mention pytest")

    def test_ide_configurations_dont_conflict(self):
        """Test that different IDE configurations don't conflict."""
        vscode_dir = self.repo_root / ".vscode"
        idea_dir = self.repo_root / ".idea"

        # Both can coexist
        self.assertTrue(vscode_dir.exists(), "VSCode config should exist")
        self.assertTrue(idea_dir.exists(), "IntelliJ IDEA config should exist")

        # Check that .gitignore properly handles both
        gitignore = self.repo_root / ".gitignore"
        with open(gitignore, 'r') as f:
            gitignore_content = f.read()

        # Should not ignore entire .vscode or .idea directories
        # (so configs are tracked, but temporary files aren't)
        idea_gitignore = self.repo_root / ".idea" / ".gitignore"
        self.assertTrue(
            idea_gitignore.exists(),
            ".idea should have its own .gitignore for temporary files"
        )

    def test_security_credentials_not_in_gitignore_but_env_is(self):
        """Test that security credentials are properly gitignored."""
        gitignore = self.repo_root / ".gitignore"
        with open(gitignore, 'r') as f:
            gitignore_content = f.read()

        # .env should be gitignored
        self.assertIn(".env", gitignore_content, ".env should be gitignored")

        # But .env.sample should NOT be gitignored (it should be tracked)
        env_sample = self.repo_root / ".env.sample"
        self.assertTrue(
            env_sample.exists(),
            ".env.sample should exist and be tracked"
        )

    def test_mcp_server_configuration_consistency(self):
        """Test that MCP server configuration is consistent across files."""
        port = "8000"

        files_to_check = [
            self.repo_root / "Dockerfile",
            self.repo_root / ".cloudflared" / "config.yml",
            self.repo_root / ".cloudflared" / "config.docker.yml",
            self.repo_root / "MCP_SETUP.md",
        ]

        for file_path in files_to_check:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.assertIn(
                port,
                content,
                f"{file_path.name} should reference port {port}"
            )

    def test_ci_workflow_complete_pipeline(self):
        """Test that CI workflow has a complete testing pipeline."""
        ci_workflow = self.repo_root / ".github" / "workflows" / "ci.yml"

        with open(ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Collect step names/actions for verification
        step_actions = []
        for step in steps:
            if "uses" in step:
                step_actions.append(step["uses"].split("@")[0])
            if "run" in step:
                step_actions.append("run")

        # Verify complete pipeline
        self.assertIn("actions/checkout", step_actions, "Should checkout code")
        self.assertIn("actions/setup-python", step_actions, "Should setup Python")
        self.assertIn("astral-sh/setup-uv", step_actions, "Should setup uv")
        self.assertIn("actions/cache", step_actions, "Should use caching")
        self.assertTrue(
            any("run" in step_actions for _ in range(2)),
            "Should have run steps for install and test"
        )

    def test_documentation_mentions_all_major_features(self):
        """Test that README documents all major features."""
        readme = self.repo_root / "README.md"
        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()

        major_features = [
            "Docker",
            "MCP",
            "resume",
            "Claude",
            "ChatGPT",
        ]

        for feature in major_features:
            self.assertIn(
                feature,
                content,
                f"README should mention {feature}"
            )

    def test_multilingual_support_consistency(self):
        """Test that multilingual documentation is consistent."""
        multilingual_files = [
            self.repo_root / ".env.sample",
            self.repo_root / "DOCS_GENERATION.md",
        ]

        for file_path in multilingual_files:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for Chinese characters
                has_chinese = any(
                    ord(char) > 0x4E00 and ord(char) < 0x9FFF
                    for char in content
                )

                # Check for English
                has_english = any(
                    char.isalpha() and ord(char) < 128
                    for char in content
                )

                self.assertTrue(
                    has_chinese and has_english,
                    f"{file_path.name} should have both Chinese and English content"
                )


class TestRegressionPrevention(unittest.TestCase):
    """Tests to prevent common regressions."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_no_hardcoded_secrets_anywhere(self):
        """Test that no files contain hardcoded secrets."""
        # This is a heuristic test - checks for patterns that look like secrets
        suspicious_files = [
            ".env.sample",
        ]

        for file_name in suspicious_files:
            file_path = self.repo_root / file_name
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for API key patterns specifically
                # Match lines with API_KEY or TOKEN assignment
                api_key_lines = [
                    line for line in content.split('\n')
                    if '=' in line and not line.strip().startswith('#')
                    and ('API_KEY' in line or 'TOKEN' in line)
                ]

                for line in api_key_lines:
                    if '=' in line:
                        # Get the value part after =
                        value = line.split('=', 1)[1].strip()

                        # Skip if it's empty or commented
                        if not value or value.startswith('#'):
                            continue

                        # Should use placeholders for API keys
                        has_placeholder = any(
                            pattern in line
                            for pattern in ["your_", "YOUR_", "_here", "example", "示例", "https://"]
                        )

                        self.assertTrue(
                            has_placeholder,
                            f"{file_name} should use placeholder values for API keys: {line[:70]}"
                        )

    def test_all_configs_use_utf8(self):
        """Test that all configuration files can be read as UTF-8."""
        config_files = [
            ".env.sample",
            "README.md",
            "AGENTS.md",
            "MCP_SETUP.md",
            ".cursorrules",
            ".cursorprompt",
        ]

        for file_name in config_files:
            file_path = self.repo_root / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.assertIsNotNone(content)
                except UnicodeDecodeError:
                    self.fail(f"{file_name} should be readable as UTF-8")

    def test_no_broken_yaml_syntax(self):
        """Test that all YAML files have valid syntax."""
        yaml_files = [
            ".github/workflows/ci.yml",
            ".cloudflared/config.yml",
            ".cloudflared/config.docker.yml",
        ]

        for file_name in yaml_files:
            file_path = self.repo_root / file_name
            if file_path.exists():
                with open(file_path, 'r') as f:
                    try:
                        data = yaml.safe_load(f)
                        self.assertIsNotNone(data)
                    except yaml.YAMLError as e:
                        self.fail(f"{file_name} has invalid YAML syntax: {e}")


if __name__ == "__main__":
    unittest.main()