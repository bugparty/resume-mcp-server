from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import requests
from fs.memoryfs import MemoryFS

from myagent import mcp_server


class _ObjectRequestHandler(BaseHTTPRequestHandler):
    stored_objects: dict[tuple[str, str], bytes] = {}

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?")[0].lstrip("/")
        if "/" not in path:
            self.send_response(400)
            self.end_headers()
            return

        bucket, key = path.split("/", 1)
        data = self.stored_objects.get((bucket, key))
        if data is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - keep signature
        """Silence default stdout logging during tests."""


def test_render_resume_pdf_uploads_and_returns_signed_url(monkeypatch):
    _ObjectRequestHandler.stored_objects.clear()
    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    memory_fs = MemoryFS()
    with memory_fs.open("test.pdf", "wb") as pdf_file:
        pdf_file.write(pdf_bytes)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _ObjectRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    monkeypatch.setenv("RESUME_S3_BUCKET_NAME", "resume-bucket")
    monkeypatch.setenv("RESUME_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("RESUME_S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("RESUME_S3_KEY_PREFIX", "resumes/")
    monkeypatch.setenv("RESUME_S3_URL_EXPIRATION", "120")

    def fake_render_resume_to_latex_tool(version: str):  # noqa: ANN001 - signature defined by tool
        return SimpleNamespace(latex="% LaTeX content")

    def fake_compile_resume_pdf_tool(latex: str, version: str):  # noqa: ANN001 - tool signature
        return SimpleNamespace(pdf_path="data://resumes/output/test.pdf")

    class FakeS3Client:
        def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str = "application/pdf") -> None:  # noqa: N802
            _ObjectRequestHandler.stored_objects[(Bucket, Key)] = Body

        def generate_presigned_url(self, ClientMethod: str, Params: dict[str, str], ExpiresIn: int) -> str:  # noqa: N802
            bucket = Params["Bucket"]
            key = Params["Key"]
            return f"http://127.0.0.1:{server.server_port}/{bucket}/{key}?signature=fake&expires={ExpiresIn}"

    fake_s3_client = FakeS3Client()

    def fake_boto3_client(*args, **kwargs):  # noqa: ANN001 - boto3 client signature is dynamic
        return fake_s3_client

    monkeypatch.setattr(mcp_server, "render_resume_to_latex_tool", fake_render_resume_to_latex_tool)
    monkeypatch.setattr(mcp_server, "compile_resume_pdf_tool", fake_compile_resume_pdf_tool)
    monkeypatch.setattr(mcp_server, "get_output_fs", lambda: memory_fs)
    monkeypatch.setattr(mcp_server.boto3, "client", fake_boto3_client)

    try:
        result = mcp_server.render_resume_pdf.fn("resume")

        expected_key = "resumes/test.pdf"
        expected_url = (
            f"http://127.0.0.1:{server.server_port}/resume-bucket/{expected_key}"
            f"?signature=fake&expires=120"
        )
        assert result == {
            "signed_url": expected_url,
            "filename": "test.pdf",
        }

        stored_pdf = _ObjectRequestHandler.stored_objects[("resume-bucket", expected_key)]
        assert stored_pdf == pdf_bytes

        download = requests.get(result["signed_url"], timeout=5)
        assert download.status_code == 200
        assert download.content == pdf_bytes
    finally:
        server.shutdown()
        server_thread.join()
