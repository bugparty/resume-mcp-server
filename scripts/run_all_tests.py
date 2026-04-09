#!/usr/bin/env python3
"""Run schema validation plus the repository's supported pytest suites."""

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

PRECHECK_COMMANDS = [
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
]

SKIPPED_PYTEST_FILES = {
    "tests/test_remote_renderer.py",
    "tests/test_tool_compile.py",
}


def _python_command() -> list[str]:
    return [sys.executable]


def _pytest_files() -> list[str]:
    test_dir = ROOT / "tests"
    files = []
    for path in sorted(test_dir.rglob("test_*.py")):
        rel_path = path.relative_to(ROOT).as_posix()
        if rel_path in SKIPPED_PYTEST_FILES:
            continue
        files.append(rel_path)
    return files


def _run_pytest_file(test_file: str, env: dict[str, str]) -> int:
    pytest_cmd = _python_command() + ["-m", "pytest", test_file]
    print(f"\n>>> Running: {' '.join(pytest_cmd)}")
    proc = subprocess.run(pytest_cmd, cwd=ROOT, env=env)
    if proc.returncode == 5:
        print(f"Skipping {test_file} (no tests collected)")
        return 0
    if proc.returncode != 0:
        print(
            f"Command failed with exit code {proc.returncode}: {' '.join(pytest_cmd)}"
        )
        return proc.returncode
    return 0


def run_commands() -> int:
    env = os.environ.copy()
    env.update(ENV_OVERRIDES)
    src_path = ROOT / "src"
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{pythonpath}" if pythonpath else str(src_path)
    )

    for cmd in PRECHECK_COMMANDS:
        print(f"\n>>> Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=ROOT, env=env)
        if proc.returncode != 0:
            print(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}")
            return proc.returncode

    for test_file in _pytest_files():
        status = _run_pytest_file(test_file, env)
        if status != 0:
            return status
    return 0


if __name__ == "__main__":
    raise SystemExit(run_commands())
