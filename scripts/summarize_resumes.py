"""Generate resume_summary.yaml using the shared resume loader helpers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from resume_platform.infrastructure.settings import load_settings
from resume_platform.infrastructure.filesystem import init_filesystems


def _extract_summary_bullets(resume_data: dict[str, Any], limit: int = 3) -> list[str]:
    for section in resume_data.get("sections", []):
        if section.get("id") == "summary" and isinstance(section.get("bullets"), list):
            return [str(item) for item in section.get("bullets", [])[:limit]]
    return []


def _extract_skills(resume_data: dict[str, Any], limit: int = 12) -> list[str]:
    skills: list[str] = []
    for section in resume_data.get("sections", []):
        if section.get("id") != "skills":
            continue
        for group in section.get("groups", []):
            items = group.get("items", []) if isinstance(group, dict) else []
            for item in items:
                text = str(item).strip()
                if not text or text in skills:
                    continue
                skills.append(text)
                if len(skills) >= limit:
                    return skills
    return skills


def _extract_entries(resume_data: dict[str, Any], limit: int = 6) -> list[str]:
    entries: list[str] = []
    for section in resume_data.get("sections", []):
        section_entries = section.get("entries", []) if isinstance(section, dict) else []
        for entry in section_entries:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            organization = str(entry.get("organization", "")).strip()
            if title and organization:
                value = f"{title} - {organization}"
            else:
                value = title or organization
            if value and value not in entries:
                entries.append(value)
                if len(entries) >= limit:
                    return entries
    return entries


def summarize_resumes_to_index(data_dir: Path, summary_path: Path) -> dict[str, str]:
    resumes_summary: list[dict[str, Any]] = []

    for resume_file in sorted(data_dir.glob("*.yaml")):
        if resume_file.name == summary_path.name:
            continue
        with resume_file.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if not isinstance(loaded, dict):
            continue

        metadata = loaded.get("metadata", {}) if isinstance(loaded.get("metadata"), dict) else {}
        resumes_summary.append(
            {
                "version": resume_file.stem,
                "metadata": {
                    "position": metadata.get("position", ""),
                    "email": metadata.get("email", ""),
                    "mobile": metadata.get("mobile", ""),
                    "github": metadata.get("github", ""),
                    "linkedin": metadata.get("linkedin", ""),
                },
                "highlights": {
                    "summary": _extract_summary_bullets(loaded),
                    "skills": _extract_skills(loaded),
                    "entries": _extract_entries(loaded),
                },
            }
        )

    payload = {"resumes": resumes_summary}
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)

    return {"yaml_path": str(summary_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    test_resume_data_dir = os.getenv("TEST_RESUME_DATA_DIR")
    test_resume_summary_path = os.getenv("TEST_RESUME_SUMMARY_PATH")

    if test_resume_data_dir and test_resume_summary_path:
        data_dir = Path(test_resume_data_dir)
        summary_path = Path(test_resume_summary_path)
    else:
        # Ensure filesystems are initialized for scripts (CI/local runtime parity)
        settings = load_settings()
        init_filesystems(settings.resume_fs_url, settings.jd_fs_url)
        data_dir = settings.data_dir
        summary_path = settings.data_dir.parent / "resume_summary.yaml"

    result = summarize_resumes_to_index(data_dir, summary_path)
    print(f"Summary written to {result['yaml_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
