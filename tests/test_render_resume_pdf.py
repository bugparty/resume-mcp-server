from __future__ import annotations

from types import SimpleNamespace

from fs.memoryfs import MemoryFS

from myagent import mcp_server


def test_render_resume_pdf_uploads_and_returns_public_url(monkeypatch):
    uploaded: dict[str, object] = {}
    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    memory_fs = MemoryFS()
    memory_fs.writebytes("test.pdf", pdf_bytes)

    monkeypatch.setenv("RESUME_S3_BUCKET_NAME", "resume-bucket")
    monkeypatch.setenv("RESUME_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("RESUME_S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("RESUME_S3_KEY_PREFIX", "resumes")
    monkeypatch.setenv("RESUME_S3_PUBLIC_BASE_URL", "https://cdn.example.com/base")

    def fake_render_resume_to_latex_tool(version: str):
        return SimpleNamespace(latex="% LaTeX content")

    def fake_compile_resume_pdf_tool(latex: str, version: str):
        return SimpleNamespace(
            pdf_path="data://resumes/output/test.pdf",
            latex_assets_dir="data://resumes/output/test_latex",
        )

    class FakeS3Client:
        def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str = "application/pdf") -> None:  # noqa: N802
            uploaded[(Bucket, Key)] = Body

        def head_object(self, Bucket: str, Key: str) -> dict[str, str]:  # noqa: N802
            if (Bucket, Key) not in stored_objects:
                raise AssertionError("head_object called before object stored")
            return {}

    fake_s3_client = FakeS3Client()

    def fake_boto3_client(*args, **kwargs):
        return fake_s3_client

    monkeypatch.setattr(mcp_server, "render_resume_to_latex_tool", fake_render_resume_to_latex_tool)
    monkeypatch.setattr(mcp_server, "compile_resume_pdf_tool", fake_compile_resume_pdf_tool)
    monkeypatch.setattr(mcp_server, "get_output_fs", lambda: memory_fs)

    def fake_upload_bytes_to_s3(
        data: bytes, filename: str, content_type: str, description: str
    ) -> tuple[str, str]:
        assert filename == "test.pdf"
        assert content_type == "application/pdf"
        assert data == pdf_bytes
        key = f"resumes/{filename}"
        return f"https://cdn.example.com/base/{key}", key

    monkeypatch.setattr(mcp_server, "upload_bytes_to_s3", fake_upload_bytes_to_s3)

    result = mcp_server.render_resume_pdf.fn("resume")

    expected_key = "resumes/test.pdf"
    expected_url = "https://cdn.example.com/base/resumes/test.pdf"

    assert result == {
        "public_url": expected_url,
        "filename": "test.pdf",
        "pdf_path": "data://resumes/output/test.pdf",
        "latex_assets_dir": "data://resumes/output/test_latex",
    }

    # Bytes were uploaded via upload_bytes_to_s3; we assert the function got the right bytes above.
