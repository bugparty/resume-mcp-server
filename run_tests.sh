#!/bin/bash
set -e

echo "=== Running All Tests ==="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE_ROOT="$ROOT_DIR/tests/fixtures/test_data"

export TEST_RESUME_DATA_DIR="$FIXTURE_ROOT/resumes"
export TEST_RESUME_SUMMARY_PATH="$FIXTURE_ROOT/resume_summary.yaml"
export TEST_RESUME_JD_DIR="$FIXTURE_ROOT/jd"
export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if [ -x ".venv/bin/pytest" ]; then
	TEST_RUNNER=(.venv/bin/pytest)
elif [ -x ".venv/Scripts/python.exe" ]; then
	TEST_RUNNER=(.venv/Scripts/python.exe -m pytest)
elif command -v uv >/dev/null 2>&1; then
	TEST_RUNNER=(uv run pytest)
elif command -v python3 >/dev/null 2>&1; then
	TEST_RUNNER=(python3 -m pytest)
else
	echo "Error: no usable python/uv command found for tests"
	exit 1
fi

mapfile -t TEST_FILES < <(find tests -name "test_*.py" -type f | sort)

for test_file in "${TEST_FILES[@]}"; do
	echo ""
	echo "=== Running $test_file ==="
	set +e
	"${TEST_RUNNER[@]}" "$test_file"
	status=$?
	set -e
	if [ "$status" -eq 5 ]; then
		echo "Skipping $test_file (no tests collected)"
		continue
	fi
	if [ "$status" -ne 0 ]; then
		exit "$status"
	fi
done

echo -e "\n=== All Tests Passed! ==="
