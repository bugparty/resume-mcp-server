from __future__ import annotations

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


def test_find_resume_versions_from_top_level(monkeypatch) -> None:
    fs = _FakeFS(
        top_level=["resume.yaml", "foo.txt", "backend.yaml"],
        recursive=[],
    )
    monkeypatch.setattr(repository, "get_resume_fs", lambda: fs)

    versions = repository.find_resume_versions()

    assert versions == ["backend", "resume"]


def test_find_resume_versions_falls_back_to_recursive_scan(monkeypatch) -> None:
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

    versions = repository.find_resume_versions()

    assert versions == ["platform", "resume"]


def test_find_resume_versions_falls_back_when_listdir_errors(monkeypatch) -> None:
    fs = _FakeFSErrorFS(
        top_level=[],
        recursive=["resumes/fallback_a.yaml", "nested/fallback_b.yaml"],
    )
    monkeypatch.setattr(repository, "get_resume_fs", lambda: fs)

    versions = repository.find_resume_versions()

    assert versions == ["fallback_a", "fallback_b"]
