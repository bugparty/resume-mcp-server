"""
Test environment configuration and .env.sample file.

This module tests that environment variable configuration is properly
structured and documented in .env.sample.
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


class TestEnvSampleStructure(unittest.TestCase):
    """Test .env.sample file structure and content."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.env_sample = self.repo_root / ".env.sample"

    def test_env_sample_exists(self):
        """Test that .env.sample exists."""
        self.assertTrue(
            self.env_sample.exists(),
            ".env.sample should exist"
        )

    def test_env_sample_readable(self):
        """Test that .env.sample is readable."""
        self.assertTrue(
            self.env_sample.is_file(),
            ".env.sample should be a file"
        )

        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertGreater(
            len(content),
            0,
            ".env.sample should not be empty"
        )

    def test_required_api_keys_documented(self):
        """Test that required API keys are documented."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for required API keys
        required_keys = [
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_BASE_URL",
        ]

        for key in required_keys:
            self.assertIn(
                key,
                content,
                f".env.sample should document {key}"
            )

    def test_optional_api_keys_documented(self):
        """Test that optional API keys are documented."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for optional API keys
        optional_keys = [
            "OPENAI_API_KEY",
            "CLOUDFLARE_GATEWAY_URL",
            "CLOUDFLARE_API_KEY",
            "LANGCHAIN_API_KEY",
        ]

        for key in optional_keys:
            self.assertIn(
                key,
                content,
                f".env.sample should document optional key {key}"
            )

    def test_data_directory_config_documented(self):
        """Test that data directory configuration is documented."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for data directory configuration
        data_config_keys = [
            "RESUME_DATA_DIR",
            "RESUME_AGGREGATE_PATH",
            "RESUME_JD_DIR",
            "LOGS_DIR",
        ]

        for key in data_config_keys:
            self.assertIn(
                key,
                content,
                f".env.sample should document {key}"
            )

    def test_langsmith_config_documented(self):
        """Test that LangSmith configuration is documented."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for LangSmith configuration
        langsmith_keys = [
            "LANGCHAIN_API_KEY",
            "LANGCHAIN_TRACING_V2",
            "LANGCHAIN_ENDPOINT",
            "LANGCHAIN_PROJECT",
        ]

        for key in langsmith_keys:
            self.assertIn(
                key,
                content,
                f".env.sample should document LangSmith config {key}"
            )

    def test_env_sample_has_comments(self):
        """Test that .env.sample has helpful comments."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for comment lines
        comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]

        self.assertGreater(
            len(comment_lines),
            10,
            ".env.sample should have helpful comments"
        )

    def test_env_variables_format(self):
        """Test that environment variables follow proper format."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Pattern for environment variable: KEY=value
        env_pattern = re.compile(r'^[A-Z_][A-Z0-9_]*=.*$')

        env_lines = [
            line.strip() for line in lines
            if line.strip() and not line.strip().startswith('#')
        ]

        for line in env_lines:
            self.assertTrue(
                env_pattern.match(line),
                f"Environment variable line should follow KEY=value format: {line}"
            )

    def test_no_actual_secrets_in_sample(self):
        """Test that .env.sample doesn't contain actual secrets."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check that sample values are placeholders
        placeholder_patterns = [
            "your_",
            "_here",
            "YOUR_",
        ]

        # Extract values from KEY=value lines
        env_lines = [
            line.strip() for line in content.split('\n')
            if '=' in line and not line.strip().startswith('#')
        ]

        has_placeholders = False
        for line in env_lines:
            if '=' in line:
                value = line.split('=', 1)[1].strip()
                if value and any(pattern in value for pattern in placeholder_patterns):
                    has_placeholders = True
                    break

        self.assertTrue(
            has_placeholders,
            ".env.sample should use placeholder values, not actual secrets"
        )

    def test_cloudflare_gateway_configuration(self):
        """Test that Cloudflare Gateway configuration is documented."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for Cloudflare-specific configuration
        self.assertIn("CLOUDFLARE_GATEWAY_URL", content, "Should document Cloudflare Gateway URL")
        self.assertIn("DEEPSEEK_BASE_URL", content, "Should document DeepSeek base URL")

        # Check that Cloudflare Gateway is mentioned in comments
        self.assertIn("Cloudflare", content, "Should mention Cloudflare in documentation")

    def test_chinese_documentation_present(self):
        """Test that Chinese documentation is present (multilingual support)."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for Chinese characters (basic check)
        # This ensures the file supports internationalization
        has_chinese = any(ord(char) > 0x4E00 and ord(char) < 0x9FFF for char in content)

        self.assertTrue(
            has_chinese,
            ".env.sample should contain Chinese documentation for international users"
        )


class TestEnvironmentVariableUsage(unittest.TestCase):
    """Test that environment variables are properly used in the codebase."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_env_file_not_in_repo(self):
        """Test that .env file is not committed to repository."""
        env_file = self.repo_root / ".env"

        # .env should ideally not exist in the repo, or if it exists for testing,
        # it should be gitignored
        gitignore = self.repo_root / ".gitignore"

        if gitignore.exists():
            with open(gitignore, 'r') as f:
                gitignore_content = f.read()

            self.assertIn(
                ".env",
                gitignore_content,
                ".env should be in .gitignore to prevent committing secrets"
            )

    def test_settings_module_exists(self):
        """Test that settings module exists for environment configuration."""
        settings_file = self.repo_root / "src" / "myagent" / "settings.py"

        self.assertTrue(
            settings_file.exists(),
            "settings.py should exist for environment configuration"
        )

    def test_dotenv_dependency_present(self):
        """Test that python-dotenv is in dependencies."""
        pyproject_file = self.repo_root / "pyproject.toml"

        with open(pyproject_file, 'r') as f:
            content = f.read()

        self.assertIn(
            "python-dotenv",
            content,
            "python-dotenv should be in dependencies for .env loading"
        )


class TestEnvironmentVariableDefaults(unittest.TestCase):
    """Test that environment variables have sensible defaults."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.env_sample = self.repo_root / ".env.sample"

    def test_data_directory_defaults(self):
        """Test that data directory defaults are reasonable."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for sensible default paths
        self.assertIn("./data/resumes", content, "Should have default resume data directory")
        self.assertIn("./data/jd", content, "Should have default JD directory")
        self.assertIn("./logs", content, "Should have default logs directory")

    def test_deepseek_base_url_example(self):
        """Test that DeepSeek base URL has proper example."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for both official and Cloudflare Gateway examples
        self.assertIn("api.deepseek.com", content, "Should mention official DeepSeek API")
        self.assertIn("gateway.ai.cloudflare.com", content, "Should mention Cloudflare Gateway option")

    def test_langchain_tracing_default(self):
        """Test that LangChain tracing has a default value."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for LangChain tracing configuration
        self.assertIn("LANGCHAIN_TRACING_V2=true", content, "Should have LangChain tracing default")


class TestSecurityConfiguration(unittest.TestCase):
    """Test security-related configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.env_sample = self.repo_root / ".env.sample"

    def test_security_warnings_present(self):
        """Test that security warnings are present in .env.sample."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for security-related warnings
        security_keywords = ["安全", "不要", "提交", "版本控制", "密钥"]

        has_security_warning = any(keyword in content for keyword in security_keywords)

        self.assertTrue(
            has_security_warning,
            ".env.sample should contain security warnings"
        )

    def test_no_hardcoded_credentials(self):
        """Test that no actual credentials are hardcoded."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check that no line contains what looks like an actual API key
        # (long alphanumeric strings that don't look like placeholders)
        lines = content.split('\n')

        for line in lines:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.split('=', 1)
                value = value.strip()

                # If value is longer than 32 chars and alphanumeric, it might be a real key
                if len(value) > 32 and value.replace('_', '').replace('-', '').isalnum():
                    # But it should contain placeholder indicators
                    self.assertTrue(
                        'your' in value.lower() or 'here' in value.lower() or
                        'example' in value.lower() or value.startswith('https://'),
                        f"Long value should be a placeholder: {key}={value[:20]}..."
                    )


class TestConfigurationDocumentation(unittest.TestCase):
    """Test that configuration is properly documented."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.env_sample = self.repo_root / ".env.sample"

    def test_configuration_sections(self):
        """Test that .env.sample is organized into sections."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for section headers (lines with = repeated)
        section_headers = [
            line for line in content.split('\n')
            if '=' in line and line.strip().startswith('#') and line.count('=') > 5
        ]

        self.assertGreater(
            len(section_headers),
            3,
            ".env.sample should be organized into clear sections"
        )

    def test_each_key_has_comment(self):
        """Test that each environment variable has explanatory comments."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find all environment variable lines
        env_lines_indices = [
            i for i, line in enumerate(lines)
            if line.strip() and '=' in line and not line.strip().startswith('#')
        ]

        # Check that each has a comment nearby (within 3 lines before)
        for idx in env_lines_indices:
            # Look for comments in the 3 lines before
            has_nearby_comment = False
            for check_idx in range(max(0, idx - 3), idx):
                if lines[check_idx].strip().startswith('#'):
                    has_nearby_comment = True
                    break

            # Allow some variables to be grouped under the same comment
            if not has_nearby_comment:
                # At least the section should have comments
                self.fail(
                    f"Environment variable at line {idx + 1} should have explanatory comments: "
                    f"{lines[idx].strip()}"
                )

    def test_usage_examples_present(self):
        """Test that usage examples are present in comments."""
        with open(self.env_sample, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for usage examples or instructions
        example_indicators = [
            "获取地址",  # Get from
            "用于",  # Used for
            "默认",  # Default
            "格式",  # Format
        ]

        has_examples = any(indicator in content for indicator in example_indicators)

        self.assertTrue(
            has_examples,
            ".env.sample should contain usage examples or instructions"
        )


if __name__ == "__main__":
    unittest.main()