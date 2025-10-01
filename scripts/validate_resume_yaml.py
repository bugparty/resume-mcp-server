"""Validate resume YAML files against the canonical JSON schema using PyYAML + jsonschema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import yaml
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "resume_schema.json"


def load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_file(path: Path, validator: Draft202012Validator) -> list[str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except Exception as exc:  # PyYAML errors
        return [f"YAML parse error in {path}: {exc}"]

    errors = [
        f"{path}: {err.message} (at {'/'.join(str(p) for p in err.path)})"
        for err in validator.iter_errors(payload)
    ]
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="YAML files or directories to validate")
    args = parser.parse_args(argv)

    schema = load_schema()
    validator = Draft202012Validator(schema)

    failures: list[str] = []
    for target in args.paths:
        path = Path(target)
        if path.is_dir():
            for file in path.rglob("*.yaml"):
                failures.extend(validate_file(file, validator))
        else:
            failures.extend(validate_file(path, validator))

    if failures:
        print("Validation errors detected:")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("All files passed schema validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
