"""Tests that the MCP server assembles runtime state explicitly, not on import.

See docs/adr/0001-composition-root-and-runtime-lifecycle.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _run(body: str, logs_dir: Path) -> str:
    """Import the server in a clean process and report on its side effects."""
    script = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        f"os.environ['LOGS_DIR'] = {str(logs_dir)!r}\n"
        "import resume_platform.interfaces.mcp.server as server\n"
        "from resume_platform.infrastructure import filesystem as fs\n"
        f"{body}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_importing_server_does_not_initialize_filesystems(tmp_path: Path) -> None:
    """Importing the server module must not touch the global filesystems.

    This used to run as an import side effect, which meant merely importing the
    server (as test collection does) pointed the process-global filesystems at
    the real data dir.
    """
    assert _run("print(fs.is_initialized())", tmp_path / "logs") == "False"


def test_importing_server_does_not_create_the_logs_dir(tmp_path: Path) -> None:
    """Resolving log paths and opening the log file are deferred to first use."""
    logs_dir = tmp_path / "logs"
    out = _run(f"print(not os.path.exists({str(logs_dir)!r}))", logs_dir)
    assert out == "True"


def test_start_server_runtime_initializes_filesystems(tmp_path: Path) -> None:
    """The entry-point helper is what actually assembles runtime state."""
    out = _run(
        "server._start_server_runtime()\n" "print(fs.is_initialized())",
        tmp_path / "logs",
    )
    assert out == "True"
