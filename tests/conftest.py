import sys
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
