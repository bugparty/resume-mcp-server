from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from urllib.parse import quote

from fs.memoryfs import MemoryFS

from myagent import mcp_server


def test_render_resume_to_overleaf_exports_zip(monkeypatch):
    latex_content = "% Generated LaTeX"
    memory_fs = MemoryFS()

    monkeypatch.setenv("RESUME_S3_BUCKET_NAME", "resume-bucket")
    monkeypatch.setenv("RESUME_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("RESUME_S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("RESUME_S3_KEY_PREFIX", "resumes")
    monkeypatch.setenv("RESUME_S3_PUBLIC_BASE_URL", "https://cdn.example.com/base")

    monkeypatch.setattr(mcp_server.time, "strftime", lambda fmt: "20250101_120000")

    def fake_render_resume_to_latex_tool(version: str):
        assert version == "resume"
        return SimpleNamespace(latex=latex_content)

    class FakeS3Client:
        def __init__(self) -> None:
            self.stored_objects: dict[tuple[str, str], bytes] = {}

        def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str = "application/zip") -> None:  # noqa: N802
            self.stored_objects[(Bucket, Key)] = Body

        def head_object(self, Bucket: str, Key: str) -> dict[str, str]:  # noqa: N802
            if (Bucket, Key) not in self.stored_objects:
                raise AssertionError("Object not uploaded before availability check")
            return {}

    fake_s3_client = FakeS3Client()

    def fake_boto3_client(*args, **kwargs):
        return fake_s3_client

    monkeypatch.setattr(mcp_server, "render_resume_to_latex_tool", fake_render_resume_to_latex_tool)
    monkeypatch.setattr(mcp_server, "get_output_fs", lambda: memory_fs)

    uploaded: dict[str, object] = {}

    def fake_upload_bytes_to_s3(
        data: bytes, filename: str, content_type: str, description: str
    ) -> tuple[str, str]:
        assert filename.endswith("_overleaf.zip")
        assert content_type == "application/zip"
        uploaded["bytes"] = data
        key = f"resumes/{filename}"
        return f"https://cdn.example.com/base/{key}", key

    monkeypatch.setattr(mcp_server, "upload_bytes_to_s3", fake_upload_bytes_to_s3)

    result = mcp_server.render_resume_to_overleaf.fn("resume")

    expected_filename = "resume_20250101_120000_overleaf.zip"
    expected_key = f"resumes/{expected_filename}"
    expected_public_url = f"https://cdn.example.com/base/{expected_key}"
    expected_overleaf_url = (
        f"https://www.overleaf.com/docs?snip_uri={quote(expected_public_url, safe='')}&engine=xelatex"
    )
    expected_zip_path = f"data://resumes/output/{expected_filename}"
    expected_latex_dir = "data://resumes/output/resume_20250101_120000_latex"

    assert result == {
        "overleaf_url": expected_overleaf_url,
        "public_url": expected_public_url,
        "filename": expected_filename,
        "zip_path": expected_zip_path,
        "latex_assets_dir": expected_latex_dir,
    }

    stored_zip = uploaded["bytes"]
    assert stored_zip == memory_fs.readbytes(expected_filename)

    assert memory_fs.isdir("resume_20250101_120000_latex")
    assert memory_fs.exists("resume_20250101_120000_latex/main.tex")

    archive = zipfile.ZipFile(io.BytesIO(stored_zip))
    try:
        names = archive.namelist()
        assert "main.tex" in names
        assert archive.read("main.tex").decode("utf-8") == latex_content
        assert any(name.startswith("fonts/") for name in names)
        assert "awesome-cv.cls" in names
    finally:
        archive.close()
