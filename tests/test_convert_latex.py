"""scripts/convert_latex_resumes.py imports legacy awesome-cv LaTeX resumes.

The samples in fixtures/latex_samples are anonymised single-file resumes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from resume_platform.paths import PROJECT_ROOT

SAMPLES = sorted((Path(__file__).parent / "fixtures" / "latex_samples").glob("*.tex"))


@pytest.fixture(scope="module")
def converter():
    path = PROJECT_ROOT / "scripts" / "convert_latex_resumes.py"
    spec = importlib.util.spec_from_file_location("convert_latex_resumes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_samples_exist() -> None:
    assert len(SAMPLES) == 3


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_header_metadata_is_extracted(converter, sample: Path) -> None:
    data = converter.convert_resume(sample)
    assert data["source"] == sample.name
    metadata = data["metadata"]
    assert {"first_name", "last_name", "position"} <= set(metadata)
    assert all(isinstance(value, str) and value for value in metadata.values())


def test_latex_inline_markup_becomes_markdown(converter) -> None:
    assert converter.latex_inline_to_markdown(r"\textbf{Go} \& Rust") == "**Go** & Rust"
