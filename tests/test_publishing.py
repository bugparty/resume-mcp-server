"""PDF / Overleaf export. Only the network edges (LaTeX compile service, S3)
are faked; rendering, asset staging and output storage are real."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.parse import quote

import boto3
import pytest
import requests

from resume_platform import publishing, resume_renderer
from resume_platform.infrastructure.filesystem import get_output_fs

FAKE_PDF = b"%PDF-1.4\n% fake\n"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self.objects[(Bucket, Key)] = Body

    def head_object(self, Bucket, Key):  # noqa: N803
        assert (Bucket, Key) in self.objects, "checked before upload"
        return {}


@pytest.fixture
def s3(monkeypatch) -> FakeS3:
    fake = FakeS3()
    monkeypatch.setenv("RESUME_S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("RESUME_S3_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("RESUME_S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("RESUME_S3_KEY_PREFIX", "resumes")
    monkeypatch.setenv("RESUME_S3_PUBLIC_BASE_URL", "https://cdn.example.com/base")
    monkeypatch.setattr(boto3, "client", lambda *a, **k: fake)
    return fake


@pytest.fixture
def frozen_time(monkeypatch) -> str:
    monkeypatch.setattr(publishing, "_timestamp", lambda: "20250101_120000")
    return "20250101_120000"


@pytest.fixture
def compile_calls(monkeypatch) -> list[set[str]]:
    """Fake the remote compiler; record which files it was sent."""
    calls: list[set[str]] = []

    def fake_compile(tex_path: Path) -> Path:
        calls.append(
            {
                p.relative_to(tex_path.parent).as_posix()
                for p in tex_path.parent.rglob("*")
            }
        )
        pdf = tex_path.with_suffix(".pdf")
        pdf.write_bytes(FAKE_PDF)
        return pdf

    monkeypatch.setattr(publishing, "compile_tex_remote", fake_compile)
    return calls


def test_publish_pdf(s3, frozen_time, compile_calls) -> None:
    result = publishing.publish_pdf("resume")

    filename = f"resume_{frozen_time}.pdf"
    assert result == {
        "public_url": f"https://cdn.example.com/base/resumes/{filename}",
        "filename": filename,
        "pdf_path": f"data://resumes/output/{filename}",
        "latex_assets_dir": f"data://resumes/output/resume_{frozen_time}_latex",
    }
    assert s3.objects[("bucket", f"resumes/{filename}")] == FAKE_PDF

    output_fs = get_output_fs()
    assert output_fs.readbytes(filename) == FAKE_PDF
    assets = f"resume_{frozen_time}_latex"
    assert output_fs.exists(f"{assets}/main.tex")
    assert output_fs.exists(f"{assets}/awesome-cv.cls")
    assert not output_fs.exists(f"{assets}/main.pdf")

    [sent] = compile_calls
    assert {"main.tex", "awesome-cv.cls"} <= sent
    assert any(name.startswith("fonts/") for name in sent)


def test_publish_overleaf(s3, frozen_time) -> None:
    result = publishing.publish_overleaf("resume")

    filename = f"resume_{frozen_time}_overleaf.zip"
    public_url = f"https://cdn.example.com/base/resumes/{filename}"
    assert result == {
        "overleaf_url": f"https://www.overleaf.com/docs?snip_uri={quote(public_url, safe='')}",
        "public_url": public_url,
        "filename": filename,
        "zip_path": f"data://resumes/output/{filename}",
        "latex_assets_dir": f"data://resumes/output/resume_{frozen_time}_latex",
    }
    zip_bytes = s3.objects[("bucket", f"resumes/{filename}")]
    assert zip_bytes == get_output_fs().readbytes(filename)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        assert "awesome-cv.cls" in names
        assert any(name.startswith("fonts/") for name in names)
        assert archive.read("main.tex").decode() == resume_renderer.render_resume(
            "resume"
        )


def test_publish_unknown_version_fails_before_any_upload(s3) -> None:
    with pytest.raises(FileNotFoundError):
        publishing.publish_overleaf("missing")
    assert s3.objects == {}


# --- compile_tex_remote ---------------------------------------------------------


class _Response:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.status_code = status
        self.text = content.decode(errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


def test_compile_tex_remote_uploads_project_and_writes_pdf(tmp_path, monkeypatch):
    tex = publishing.stage_latex_project(r"\documentclass{article}", tmp_path)
    captured = {}

    def fake_post(url, files, data, timeout):
        captured.update(url=url, names={name for _, (name, _) in files}, data=data)
        return _Response(FAKE_PDF)

    monkeypatch.setattr(requests, "post", fake_post)
    pdf = resume_renderer.compile_tex_remote(tex, api_base_url="https://latex.test/")

    assert pdf.read_bytes() == FAKE_PDF
    assert captured["url"] == "https://latex.test/v1/compile"
    assert captured["data"] == {"main": "main.tex"}
    assert "main.tex" in captured["names"] and "awesome-cv.cls" in captured["names"]


def test_compile_tex_remote_wraps_http_errors(tmp_path, monkeypatch):
    tex = publishing.stage_latex_project("x", tmp_path)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Response(b"bad tex", 422))
    with pytest.raises(RuntimeError, match="Remote compilation failed"):
        resume_renderer.compile_tex_remote(tex, api_base_url="https://latex.test")
