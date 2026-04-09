#!/bin/bash
set -euo pipefail

echo "=== Running All Tests ==="

# Clear any Windows-side VIRTUAL_ENV that may leak into the devcontainer
unset VIRTUAL_ENV

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v uv >/dev/null 2>&1; then
    exec uv run python "$ROOT_DIR/scripts/run_all_tests.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 "$ROOT_DIR/scripts/run_all_tests.py" "$@"
else
    echo "Error: no usable python/uv command found for tests"
    exit 1
fi
