"""Run schema validation, targeted pytest suites, and integration tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "test_data"

ENV_OVERRIDES = {
    "TEST_RESUME_DATA_DIR": str(FIXTURE_ROOT / "resumes"),
    "TEST_RESUME_SUMMARY_PATH": str(FIXTURE_ROOT / "resume_summary.yaml"),
    "TEST_RESUME_JD_DIR": str(FIXTURE_ROOT / "jd"),
}

COMMANDS = [
    [
        "uv",
        "run",
        "python",
        str(ROOT / "scripts" / "summarize_resumes.py"),
    ],
    [
        "uv",
        "run",
        "python",
        str(ROOT / "scripts" / "validate_resume_yaml.py"),
        str(ROOT / "data" / "resumes"),
    ],
    [
        "uv",
        "run",
        "pytest",
        "tests/test_quick_toolkit.py",
        "tests/test_quick_version_workflow.py",
        "tests/test_resume_operations.py",
        "tests/test_basic_functions.py",
        "tests/test_resume_rendering.py",
    ],
]


def run_commands() -> int:
    env = os.environ.copy()
    env.update(ENV_OVERRIDES)
    src_path = ROOT / "src"
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{pythonpath}" if pythonpath else str(src_path)
    )

    for cmd in COMMANDS:
        print(f"\n>>> Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=ROOT, env=env)
        if proc.returncode != 0:
            print(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}")
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(run_commands())
