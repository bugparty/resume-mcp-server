#!/usr/bin/env bash
set -euo pipefail

# Activate virtualenv created by uv
if [ -d "/app/.venv" ]; then
  # shellcheck disable=SC1091
  source /app/.venv/bin/activate
fi

# Print basic info
echo "Starting Resume MCP Server container..."
echo "Ensuring environment (.env) if present is loaded..."
if [ -f "/app/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . /app/.env
  set +a
fi

echo
echo "Starting MCP server (HTTP) on 0.0.0.0:8000..."

# Ensure dependencies are installed (fallback) if not present in venv
if ! python -c 'import starlette' >/dev/null 2>&1; then
  echo "Dependencies not found in venv; syncing with uv..."
  if command -v uv >/dev/null 2>&1; then
    uv sync --frozen || uv sync || true
  fi
fi

# Start MCP server bound to all interfaces for container networking
python -c 'import sys; import os; sys.path.insert(0, "/app/src"); from resume_platform.interfaces.mcp.server import main; main(transport="http", port=8000)'

echo
echo "MCP server exited."

