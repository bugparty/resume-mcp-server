#!/usr/bin/env bash
set -euo pipefail

# Activate virtualenv created by uv
if [ -d "/app/.venv" ]; then
  # shellcheck disable=SC1091
  source /app/.venv/bin/activate
fi

# Colors
GREEN="\033[1;32m"
NC="\033[0m"

# Print basic info
echo "Starting Resume MCP Server container..."
echo "Ensuring environment (.env) if present is loaded..."
if [ -f "/app/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . /app/.env
  set +a
fi

# Start Cloudflare tunnel in the background and capture the public URL
LOCAL_URL="http://localhost:8000"
echo "Launching Cloudflare tunnel to ${LOCAL_URL}..."
TUNNEL_LOG="/tmp/cloudflared.log"
cloudflared tunnel --no-autoupdate --url "${LOCAL_URL}" --metrics localhost:0 >"${TUNNEL_LOG}" 2>&1 &
CLOUDFLARED_PID=$!

# Wait for the URL to appear in logs
TUNNEL_URL=""
echo "Waiting for Cloudflare public URL..."
for i in {1..60}; do
  if grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "${TUNNEL_LOG}" >/dev/null 2>&1; then
    TUNNEL_URL=$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "${TUNNEL_LOG}" | head -n1)
    break
  fi
  sleep 1
done

if [ -z "${TUNNEL_URL}" ]; then
  echo "Warning: Could not detect Cloudflare URL from logs; falling back to reading entire log:"
  echo "----- cloudflared log -----"
  tail -n +1 "${TUNNEL_LOG}" || true
  echo "---------------------------"
else
  # Append /mcp suffix for client configuration display
  TUNNEL_DISPLAY_URL="${TUNNEL_URL%/}/mcp"
  # Print in green for visibility
  echo -e "${GREEN}Cloudflare Tunnel Ready: ${TUNNEL_DISPLAY_URL}${NC}"
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
python -c 'import sys; import os; sys.path.insert(0, "/app/src"); from myagent.mcp_server import main; main(transport="http", port=8000)'

# If MCP server exits, stop cloudflared
if kill -0 ${CLOUDFLARED_PID} 2>/dev/null; then
  kill ${CLOUDFLARED_PID} || true
fi

echo
echo "If you are using ChatGPT MCP client, configure the server URL as:"
if [ -n "${TUNNEL_URL:-}" ]; then
  # Ensure display URL is set (if not from above)
  TUNNEL_DISPLAY_URL="${TUNNEL_DISPLAY_URL:-${TUNNEL_URL%/}/mcp}"
  echo "  ${TUNNEL_DISPLAY_URL}"
  # Reprint as the final line in green for easy copy/paste
  echo -e "${GREEN}Cloudflare Tunnel Ready: ${TUNNEL_DISPLAY_URL}${NC}"
else
  echo "  <cloudflare-url> (check logs above)"
fi

