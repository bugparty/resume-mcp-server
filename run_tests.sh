#!/usr/bin/env bash
# Single entry point for the test suite (used locally and in CI).
# Extra arguments are passed straight to pytest, e.g. ./run_tests.sh -k layout
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
unset VIRTUAL_ENV  # avoid leaking a host venv into the devcontainer

uv run pytest --cov --cov-config="$PWD/pyproject.toml" --cov-report=term "$@"
