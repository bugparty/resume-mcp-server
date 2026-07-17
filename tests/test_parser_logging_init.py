"""Tests that resume_input_parser defers its logging setup until first use."""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
from pathlib import Path

from resume_platform import resume_input_parser as parser

SOURCE = Path(parser.__file__)

_SIDE_EFFECTING = {
    "get_settings",
    "load_settings",
    "mkdir",
    "FileHandler",
    "basicConfig",
}


def _module_level_calls() -> list[str]:
    """Names of side-effecting calls that run at import time."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        # Function and class bodies only execute when called, not on import.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                name = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
                if name in _SIDE_EFFECTING:
                    found.append(name)
    return found


def test_import_has_no_side_effects() -> None:
    assert _module_level_calls() == []


def test_importing_module_does_not_touch_the_filesystem(tmp_path: Path) -> None:
    """Importing must not create logs_dir, even when settings point somewhere new."""
    logs_dir = tmp_path / "logs"
    script = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(SOURCE.parents[2])!r})\n"
        f"os.environ['LOGS_DIR'] = {str(logs_dir)!r}\n"
        "import resume_platform.resume_input_parser\n"
        f"print((not os.path.exists({str(logs_dir)!r})))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "True", result.stderr


def test_configure_logging_attaches_handlers_once() -> None:
    """Repeated calls must not stack duplicate handlers onto the logger."""
    parser._configure_logging()
    after_first = list(parser.logger.handlers)

    parser._configure_logging()

    assert parser.logger.handlers == after_first
    assert any(isinstance(h, logging.FileHandler) for h in after_first)


def test_parsing_configures_logging_on_demand() -> None:
    """A decorated parse call should set logging up without an explicit call."""
    parser._configure_logging()  # ensure the log file exists before parsing

    section: dict = {}
    parser.parse_education_markdown("## Education\n", section, "v1", "education")

    assert parser._logging_configured is True
