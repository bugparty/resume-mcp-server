#!/bin/bash
set -e

echo "=== Running Unit Tests ==="
# Running pytest for standard tests
# Ignoring legacy run_all_tests.py as we use pytest
pytest tests/test_basic_functions.py tests/test_resume_operations.py tests/test_resume_rendering.py

echo -e "\n=== Running Remote/API Tests ==="
# These tests require the server to be running or mock it internally
# test_multi_file_upload.py, test_remote_renderer.py, test_tool_compile.py all include server startup logic
python tests/test_multi_file_upload.py
python tests/test_remote_renderer.py
python tests/test_tool_compile.py

echo -e "\n=== All Tests Passed! ==="
