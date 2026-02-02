#!/bin/bash

set -euo pipefail

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    python -m venv .venv
    source .venv/bin/activate
fi

uv sync