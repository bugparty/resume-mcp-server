"""Generate resume_summary.yaml using the shared resume loader helpers."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from myagent.resume_loader import summarize_resumes_to_index
from myagent.settings import load_settings
from myagent.filesystem import init_filesystems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # Ensure filesystems are initialized for scripts (CI/local)
    settings = load_settings()
    init_filesystems(settings.resume_fs_url, settings.jd_fs_url)
    result = summarize_resumes_to_index()
    print(f"Summary written to {result['yaml_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
