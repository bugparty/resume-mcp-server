import sys
from unittest.mock import MagicMock
import pytest

# Mock dependencies globally before any test collection happens
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain"] = MagicMock()
sys.modules["langchain.tools"] = MagicMock()
sys.modules["langchain.tools.StructuredTool"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_anthropic"] = MagicMock()
sys.modules["rapidfuzz"] = MagicMock()
# Mock process.extract to return a list of (match, score, index) tuples
sys.modules["rapidfuzz"].process.extract.return_value = [("experience", 90, 1)]

