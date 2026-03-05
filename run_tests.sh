#!/bin/bash
set -e

echo "=== Running Unit Tests ==="
# Running pytest for standard tests
# Ignoring legacy run_all_tests.py as we use pytest
if [ -x ".venv/bin/pytest" ]; then
	.venv/bin/pytest tests/test_basic_functions.py tests/test_resume_operations.py tests/test_resume_rendering.py
elif [ -x ".venv/Scripts/python.exe" ]; then
	.venv/Scripts/python.exe -m pytest tests/test_basic_functions.py tests/test_resume_operations.py tests/test_resume_rendering.py
elif command -v uv >/dev/null 2>&1; then
	uv run pytest tests/test_basic_functions.py tests/test_resume_operations.py tests/test_resume_rendering.py
elif command -v python3 >/dev/null 2>&1; then
	python3 -m pytest tests/test_basic_functions.py tests/test_resume_operations.py tests/test_resume_rendering.py
else
	echo "Error: no usable python/uv command found for tests"
	exit 1
fi

echo -e "\n=== All Tests Passed! ==="
