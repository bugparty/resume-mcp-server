import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# These files are manual integration/debug scripts, not pytest suites.
# Ignoring them keeps test discovery responsive in VS Code and CLI pytest.
collect_ignore = [
    "test_remote_renderer.py",
    "test_tool_compile.py",
]

# Mock dependencies globally before any test collection happens
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain"] = MagicMock()
sys.modules["langchain.tools"] = MagicMock()
sys.modules["langchain.tools.StructuredTool"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_anthropic"] = MagicMock()
sys.modules["rapidfuzz"] = MagicMock()
# Mock process.extract to return a list of (match, score, index) tuples
sys.modules["rapidfuzz"].process.extract.return_value = [("experience", 90, 1)]


_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "test_data"


def _test_settings_overrides() -> dict:
    """Settings overrides that point the suite at the test fixture tree."""
    return {
        "data_dir": os.getenv("TEST_RESUME_DATA_DIR") or (_FIXTURE_ROOT / "resumes"),
        "jd_dir": os.getenv("TEST_RESUME_JD_DIR") or (_FIXTURE_ROOT / "jd"),
    }


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_runtime():
    """Assemble runtime state once for the whole session.

    Replaces the per-module ``load_settings()`` + ``init_filesystems()`` blocks
    that each test file used to run at import time. Because those ran during
    collection against process-global singletons, the first-imported module won
    and any test that reset the globals broke every later one (see #15). Routing
    through the single composition root makes the suite order-independent.

    ``force=True`` is required until PR-2 removes the import-time
    ``_ensure_server_filesystems_initialized()`` in the MCP server module: that
    side effect runs during collection (whenever a test file imports the server)
    and points the filesystems at the *real* data dir. Forcing here overrides it
    so the suite always runs against the fixture tree, regardless of what got
    imported first.
    """
    from resume_platform.infrastructure.bootstrap import bootstrap

    bootstrap(force=True, **_test_settings_overrides())


@pytest.fixture
def reset_runtime_after():
    """Rebuild the session runtime after a test mutates the global filesystems.

    Use in tests that call ``reset_filesystems()`` / ``init_filesystems()`` with
    their own directories. On teardown this force-rebuilds the fixture-backed
    filesystems, so later tests see the baseline regardless of what the test
    left behind (or whether it raised partway through).
    """
    from resume_platform.infrastructure.bootstrap import bootstrap

    try:
        yield
    finally:
        bootstrap(force=True, **_test_settings_overrides())
