"""Every resume YAML shipped in the repo must satisfy the canonical schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "resume_schema.json").read_text("utf-8"))

YAML_FILES = sorted(
    [
        ROOT / "templates" / "resume_template.yaml",
        *(ROOT / "tests" / "fixtures" / "test_data" / "resumes").glob("*.yaml"),
        *(ROOT / "data" / "resumes").glob("*.yaml"),
    ]
)


@pytest.mark.parametrize("path", YAML_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_resume_yaml_matches_schema(path: Path) -> None:
    payload = yaml.safe_load(path.read_text("utf-8"))
    errors = [
        f"{'/'.join(map(str, err.path))}: {err.message}"
        for err in Draft202012Validator(SCHEMA).iter_errors(payload)
    ]
    assert not errors, "\n".join(errors)
