"""
Test CI workflow configuration and validation.

This module tests that GitHub Actions CI workflow is properly configured
and contains all necessary steps for continuous integration.
"""

import os
import sys
import unittest
import yaml
from pathlib import Path

# Add src directory to Python path for module imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class TestGitHubActionsWorkflow(unittest.TestCase):
    """Test GitHub Actions CI workflow configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.workflows_dir = self.repo_root / ".github" / "workflows"
        self.ci_workflow = self.workflows_dir / "ci.yml"

    def test_workflows_directory_exists(self):
        """Test that .github/workflows directory exists."""
        self.assertTrue(
            self.workflows_dir.exists(),
            ".github/workflows directory should exist"
        )
        self.assertTrue(
            self.workflows_dir.is_dir(),
            ".github/workflows should be a directory"
        )

    def test_ci_workflow_exists(self):
        """Test that ci.yml workflow exists."""
        self.assertTrue(
            self.ci_workflow.exists(),
            "ci.yml workflow should exist"
        )

    def test_ci_workflow_valid_yaml(self):
        """Test that ci.yml is valid YAML."""
        with open(self.ci_workflow, 'r') as f:
            try:
                workflow = yaml.safe_load(f)
                self.assertIsNotNone(workflow, "ci.yml should be valid YAML")
            except yaml.YAMLError as e:
                self.fail(f"ci.yml is not valid YAML: {e}")

    def test_ci_workflow_has_name(self):
        """Test that CI workflow has a name."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        self.assertIn("name", workflow, "Workflow should have a name")
        self.assertEqual(workflow["name"], "CI", "Workflow name should be 'CI'")

    def test_ci_workflow_trigger_configuration(self):
        """Test that CI workflow has proper trigger configuration."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # YAML parses "on" as boolean True, so check for either "on" or True
        trigger_key = "on" if "on" in workflow else (True if True in workflow else None)
        self.assertIsNotNone(trigger_key, "Workflow should have trigger configuration")

        triggers = workflow[trigger_key]

        # Check for push trigger
        self.assertIn("push", triggers, "Workflow should trigger on push")
        if isinstance(triggers["push"], dict):
            self.assertIn("branches", triggers["push"], "Push trigger should specify branches")
            branches = triggers["push"]["branches"]
            self.assertTrue(
                "main" in branches or "master" in branches,
                "Push trigger should include main/master branch"
            )

        # Check for pull_request trigger
        self.assertIn("pull_request", triggers, "Workflow should trigger on pull requests")
        if isinstance(triggers["pull_request"], dict):
            self.assertIn("branches", triggers["pull_request"], "PR trigger should specify branches")

    def test_ci_workflow_has_jobs(self):
        """Test that CI workflow has jobs defined."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        self.assertIn("jobs", workflow, "Workflow should have jobs")
        self.assertGreater(len(workflow["jobs"]), 0, "Workflow should have at least one job")

    def test_ci_workflow_test_job_exists(self):
        """Test that CI workflow has a test job."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})
        self.assertIn("test", jobs, "Workflow should have a 'test' job")

    def test_test_job_runs_on_ubuntu(self):
        """Test that test job runs on Ubuntu."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        self.assertIn("runs-on", test_job, "Test job should specify runs-on")
        self.assertIn("ubuntu", test_job["runs-on"], "Test job should run on Ubuntu")

    def test_test_job_has_steps(self):
        """Test that test job has steps defined."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        self.assertIn("steps", test_job, "Test job should have steps")
        self.assertGreater(len(test_job["steps"]), 0, "Test job should have at least one step")

    def test_checkout_step_exists(self):
        """Test that test job checks out repository."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find checkout step
        checkout_steps = [
            step for step in steps
            if "uses" in step and "checkout" in step["uses"]
        ]

        self.assertGreater(
            len(checkout_steps),
            0,
            "Test job should have a checkout step"
        )

    def test_python_setup_step_exists(self):
        """Test that test job sets up Python."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find Python setup step
        python_steps = [
            step for step in steps
            if "uses" in step and "setup-python" in step["uses"]
        ]

        self.assertGreater(
            len(python_steps),
            0,
            "Test job should have a Python setup step"
        )

    def test_python_version_specified(self):
        """Test that Python version is specified."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find Python setup step
        python_steps = [
            step for step in steps
            if "uses" in step and "setup-python" in step["uses"]
        ]

        self.assertGreater(len(python_steps), 0, "Should have Python setup step")

        python_step = python_steps[0]
        self.assertIn("with", python_step, "Python setup should have 'with' configuration")
        self.assertIn(
            "python-version",
            python_step["with"],
            "Python setup should specify version"
        )

        # Check that it's Python 3.12 as per project requirements
        python_version = str(python_step["with"]["python-version"])
        self.assertIn("3.12", python_version, "Should use Python 3.12")

    def test_uv_installation_step_exists(self):
        """Test that test job installs uv package manager."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find uv installation step
        uv_steps = [
            step for step in steps
            if ("uses" in step and "setup-uv" in step["uses"]) or
               ("name" in step and "uv" in step["name"].lower())
        ]

        self.assertGreater(
            len(uv_steps),
            0,
            "Test job should install uv package manager"
        )

    def test_dependency_installation_step_exists(self):
        """Test that test job installs dependencies."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find dependency installation step
        install_steps = [
            step for step in steps
            if "run" in step and (
                "uv sync" in step["run"] or
                "install" in step.get("name", "").lower()
            )
        ]

        self.assertGreater(
            len(install_steps),
            0,
            "Test job should install dependencies"
        )

    def test_test_execution_step_exists(self):
        """Test that test job runs tests."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find test execution step
        test_steps = [
            step for step in steps
            if "run" in step and (
                "pytest" in step["run"] or
                "run_all_tests.py" in step["run"] or
                "test" in step.get("name", "").lower()
            )
        ]

        self.assertGreater(
            len(test_steps),
            0,
            "Test job should execute tests"
        )

    def test_environment_variables_configured(self):
        """Test that test job configures environment variables."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find test execution step with env vars
        test_steps = [
            step for step in steps
            if "run" in step and (
                "pytest" in step["run"] or
                "run_all_tests.py" in step["run"]
            )
        ]

        if test_steps:
            test_step = test_steps[0]
            self.assertIn(
                "env",
                test_step,
                "Test execution step should configure environment variables"
            )

            # Check for API key placeholders
            env_vars = test_step["env"]
            api_keys = ["GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]

            for key in api_keys:
                self.assertIn(
                    key,
                    env_vars,
                    f"Test environment should configure {key}"
                )

    def test_cache_configuration_exists(self):
        """Test that workflow uses caching for performance."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find cache step
        cache_steps = [
            step for step in steps
            if "uses" in step and "cache" in step["uses"]
        ]

        self.assertGreater(
            len(cache_steps),
            0,
            "Test job should use caching for performance"
        )

    def test_cache_key_configured(self):
        """Test that cache uses proper key configuration."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find cache step
        cache_steps = [
            step for step in steps
            if "uses" in step and "cache" in step["uses"]
        ]

        if cache_steps:
            cache_step = cache_steps[0]
            self.assertIn("with", cache_step, "Cache step should have 'with' configuration")

            cache_config = cache_step["with"]
            self.assertIn("path", cache_config, "Cache should specify paths")
            self.assertIn("key", cache_config, "Cache should have a key")

            # Check that key uses lock file for invalidation
            cache_key = cache_config["key"]
            self.assertTrue(
                "uv.lock" in cache_key or "pyproject.toml" in cache_key,
                "Cache key should depend on dependency files"
            )


class TestWorkflowStepOrder(unittest.TestCase):
    """Test that CI workflow steps are in correct order."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.ci_workflow = self.repo_root / ".github" / "workflows" / "ci.yml"

    def test_checkout_before_python_setup(self):
        """Test that checkout happens before Python setup."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find step indices
        checkout_idx = None
        python_idx = None

        for i, step in enumerate(steps):
            if "uses" in step:
                if "checkout" in step["uses"]:
                    checkout_idx = i
                elif "setup-python" in step["uses"]:
                    python_idx = i

        self.assertIsNotNone(checkout_idx, "Should have checkout step")
        self.assertIsNotNone(python_idx, "Should have Python setup step")
        self.assertLess(
            checkout_idx,
            python_idx,
            "Checkout should happen before Python setup"
        )

    def test_python_setup_before_dependencies(self):
        """Test that Python setup happens before installing dependencies."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find step indices
        python_idx = None
        install_idx = None

        for i, step in enumerate(steps):
            if "uses" in step and "setup-python" in step["uses"]:
                python_idx = i
            elif "run" in step and "uv sync" in step["run"]:
                install_idx = i

        self.assertIsNotNone(python_idx, "Should have Python setup step")
        self.assertIsNotNone(install_idx, "Should have dependency installation step")
        self.assertLess(
            python_idx,
            install_idx,
            "Python setup should happen before dependency installation"
        )

    def test_dependencies_before_tests(self):
        """Test that dependencies are installed before running tests."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find step indices
        install_idx = None
        test_idx = None

        for i, step in enumerate(steps):
            if "run" in step:
                if "uv sync" in step["run"]:
                    install_idx = i
                elif "run_all_tests.py" in step["run"] or "pytest" in step["run"]:
                    test_idx = i

        self.assertIsNotNone(install_idx, "Should have dependency installation step")
        self.assertIsNotNone(test_idx, "Should have test execution step")
        self.assertLess(
            install_idx,
            test_idx,
            "Dependencies should be installed before running tests"
        )


class TestWorkflowBestPractices(unittest.TestCase):
    """Test that workflow follows best practices."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.ci_workflow = self.repo_root / ".github" / "workflows" / "ci.yml"

    def test_all_steps_have_names(self):
        """Test that all steps have descriptive names."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Most steps should have names for clarity
        named_steps = [step for step in steps if "name" in step]

        # At least 80% of steps should have names
        name_ratio = len(named_steps) / len(steps)
        self.assertGreater(
            name_ratio,
            0.8,
            "Most steps should have descriptive names"
        )

    def test_uses_recent_action_versions(self):
        """Test that workflow uses recent versions of actions."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        for step in steps:
            if "uses" in step:
                action = step["uses"]

                # Check for version pinning
                if "@" in action:
                    version = action.split("@")[1]

                    # Should use v4+ for checkout, v5+ for setup-python, etc.
                    if "checkout" in action:
                        self.assertTrue(
                            version.startswith("v") and int(version[1]) >= 4,
                            f"Checkout action should use v4 or later: {action}"
                        )
                    elif "setup-python" in action:
                        self.assertTrue(
                            version.startswith("v") and int(version[1]) >= 4,
                            f"Setup Python action should use v4 or later: {action}"
                        )

    def test_workflow_uses_venv_activation(self):
        """Test that workflow properly activates virtual environment."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find steps that run commands
        run_steps = [step for step in steps if "run" in step]

        # Check for venv activation in run steps
        venv_activation_found = False
        for step in run_steps:
            if "source .venv/bin/activate" in step["run"]:
                venv_activation_found = True
                break

        self.assertTrue(
            venv_activation_found,
            "Workflow should activate virtual environment before running commands"
        )


class TestCIWorkflowRobustness(unittest.TestCase):
    """Test CI workflow robustness and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo_root = Path(__file__).resolve().parents[1]
        self.ci_workflow = self.repo_root / ".github" / "workflows" / "ci.yml"

    def test_workflow_handles_missing_env_vars(self):
        """Test that workflow provides empty env vars for tests."""
        with open(self.ci_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        steps = test_job["steps"]

        # Find test execution step
        test_steps = [
            step for step in steps
            if "run" in step and "run_all_tests.py" in step["run"]
        ]

        if test_steps:
            test_step = test_steps[0]
            env_vars = test_step.get("env", {})

            # Check that API keys are provided (even if empty) to avoid runtime errors
            api_keys = ["GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]
            for key in api_keys:
                self.assertIn(key, env_vars, f"Test should provide {key} to avoid errors")

    def test_workflow_file_syntax(self):
        """Test that workflow file has no syntax errors."""
        with open(self.ci_workflow, 'r') as f:
            try:
                workflow = yaml.safe_load(f)

                # Basic structure validation
                self.assertIsInstance(workflow, dict, "Workflow should be a dictionary")
                self.assertIn("jobs", workflow, "Workflow should have jobs")
                self.assertIsInstance(workflow["jobs"], dict, "Jobs should be a dictionary")

            except Exception as e:
                self.fail(f"Workflow file has syntax errors: {e}")


if __name__ == "__main__":
    unittest.main()