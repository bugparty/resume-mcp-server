from __future__ import annotations

import pytest
from fs.errors import FSError

from resume_platform.resume import repository


class _FakeWalk:
    def __init__(self, entries: list[str]) -> None:
        self._entries = entries

    def files(self, filter=None):
        return list(self._entries)


class _FakeFS:
    def __init__(self, top_level: list[str], recursive: list[str]) -> None:
        self._top_level = top_level
        self.walk = _FakeWalk(recursive)

    def listdir(self, path: str):
        assert path == "."
        return list(self._top_level)


class _FakeFSErrorFS(_FakeFS):
    def listdir(self, path: str):
        raise FSError("simulated listdir failure")


def test_list_versions_from_top_level(monkeypatch) -> None:
    fs = _FakeFS(
        top_level=["resume.yaml", "foo.txt", "backend.yaml"],
        recursive=[],
    )
    monkeypatch.setattr(repository, "get_resume_fs", lambda: fs)

    versions = repository.list_versions()

    assert versions == ["backend", "resume"]


def test_list_versions_falls_back_to_recursive_scan(monkeypatch) -> None:
    fs = _FakeFS(
        top_level=[],
        recursive=[
            "resumes/resume.yaml",
            "/nested/platform.yaml",
            "resumes/ignore.txt",
            "resumes/resume.yaml",
        ],
    )
    monkeypatch.setattr(repository, "get_resume_fs", lambda: fs)

    versions = repository.list_versions()

    assert versions == ["platform", "resume"]


def test_list_versions_falls_back_when_listdir_errors(monkeypatch) -> None:
    fs = _FakeFSErrorFS(
        top_level=[],
        recursive=["resumes/fallback_a.yaml", "nested/fallback_b.yaml"],
    )
    monkeypatch.setattr(repository, "get_resume_fs", lambda: fs)

    versions = repository.list_versions()

    assert versions == ["fallback_a", "fallback_b"]


def test_load_resume_round_trips_through_save() -> None:
    data = repository.load_resume("resume")
    data["metadata"]["first_name"] = "Ada"
    repository.save_resume("resume", data)
    assert repository.load_resume("resume")["metadata"]["first_name"] == "Ada"


def test_load_missing_version_raises() -> None:
    with pytest.raises(repository.ResumeNotFoundError, match="nope"):
        repository.load_resume("nope")


def test_load_rejects_non_mapping_document() -> None:
    from resume_platform.infrastructure.filesystem import get_resume_fs

    get_resume_fs().writetext("broken.yaml", "- just\n- a list\n")
    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        repository.load_resume("broken")


@pytest.mark.parametrize(
    "name", ["", "  ", "resume.yaml", "../etc/passwd", "a/b", ".hidden", "with space"]
)
def test_invalid_version_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        repository.validate_version_name(name)


@pytest.mark.parametrize("name", ["resume", "resume_google-swe", "v1.2"])
def test_valid_version_names(name: str) -> None:
    assert repository.validate_version_name(f" {name} ") == name


def test_find_section_suggests_closest_id() -> None:
    data = repository.load_resume("resume")
    with pytest.raises(repository.SectionNotFoundError) as exc_info:
        repository.find_section(data, "experiance")
    assert "Did you mean 'experience'?" in str(exc_info.value)
