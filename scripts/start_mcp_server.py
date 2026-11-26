"""Start the Resume MCP server (same as the ``resume-mcp`` console script).

uv run python scripts/start_mcp_server.py                     # stdio
uv run python scripts/start_mcp_server.py --transport http --port 8000
"""

from resume_platform.interfaces.mcp.server import cli

if __name__ == "__main__":
    cli()
