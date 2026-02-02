#!/bin/bash

set -euo pipefail

uv run python scripts/start_mcp_server.py --transport http --port 8000