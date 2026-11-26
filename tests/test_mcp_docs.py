"""docs/mcp_tools.md must match the live tool definitions."""

import importlib.util

from resume_platform.paths import PROJECT_ROOT


def test_tool_reference_is_up_to_date() -> None:
    path = PROJECT_ROOT / "scripts" / "generate_mcp_docs.py"
    spec = importlib.util.spec_from_file_location("generate_mcp_docs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0, (
        "Tool definitions changed: run `uv run python scripts/generate_mcp_docs.py`"
    )
