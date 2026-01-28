from __future__ import annotations

import io
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from celery.result import AsyncResult

from .resume_renderer import render_resume
from .s3_utils import upload_bytes_to_s3

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = PROJECT_ROOT / "templates"


@dataclass(frozen=True)
class LatexJobArtifacts:
    job_id: str
    latex_object_key: str
    assets_object_key: str
    output_filename: str


def _get_job_prefix() -> str:
    prefix = os.getenv("RESUME_PDF_JOB_PREFIX", "resume-jobs/")
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


def _add_path_to_zip(zip_handle: zipfile.ZipFile, path: Path, base_dir: Path) -> None:
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_file():
                arcname = child.relative_to(base_dir).as_posix()
                zip_handle.write(child, arcname)
        return
    arcname = path.relative_to(base_dir).as_posix()
    zip_handle.write(path, arcname)


def build_assets_zip_bytes(templates_root: Path | None = None) -> bytes:
    templates_root = templates_root or TEMPLATES_ROOT
    if not templates_root.exists():
        raise FileNotFoundError(f"Templates root not found: {templates_root}")

    assets = [
        templates_root / "awesome-cv.cls",
        templates_root / "profile.png",
        templates_root / "fonts",
        templates_root / "latex",
    ]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        for asset in assets:
            if asset.exists():
                _add_path_to_zip(zip_handle, asset, templates_root)
    return buffer.getvalue()


def render_resume_to_s3_artifacts(
    version: str, job_id: str | None = None
) -> LatexJobArtifacts:
    job_id = job_id or uuid.uuid4().hex
    job_prefix = _get_job_prefix()
    latex_filename = f"{job_prefix}{job_id}/resume.tex"
    assets_filename = f"{job_prefix}{job_id}/assets.zip"
    output_filename = f"{job_prefix}{job_id}/resume.pdf"

    latex_content = render_resume(version)
    assets_zip = build_assets_zip_bytes()

    _, latex_object_key = upload_bytes_to_s3(
        latex_content.encode("utf-8"),
        latex_filename,
        "text/x-tex",
        "resume LaTeX",
    )
    _, assets_object_key = upload_bytes_to_s3(
        assets_zip,
        assets_filename,
        "application/zip",
        "resume assets bundle",
    )

    return LatexJobArtifacts(
        job_id=job_id,
        latex_object_key=latex_object_key,
        assets_object_key=assets_object_key,
        output_filename=output_filename,
    )


def enqueue_compile_job(artifacts: LatexJobArtifacts) -> str:
    from .latex_worker import celery_app, LATEX_COMPILE_TASK_NAME

    async_result = celery_app.send_task(
        LATEX_COMPILE_TASK_NAME,
        kwargs={
            "job_id": artifacts.job_id,
            "latex_object_key": artifacts.latex_object_key,
            "assets_object_key": artifacts.assets_object_key,
            "output_filename": artifacts.output_filename,
        },
    )
    return async_result.id


def submit_resume_pdf_job(version: str) -> dict[str, str]:
    artifacts = render_resume_to_s3_artifacts(version)
    task_id = enqueue_compile_job(artifacts)
    return {"job_id": artifacts.job_id, "task_id": task_id, "status": "queued"}


def get_resume_pdf_job_status(task_id: str) -> dict[str, str]:
    from .latex_worker import celery_app

    result = AsyncResult(task_id, app=celery_app)
    payload: dict[str, str] = {"task_id": task_id, "state": result.state}
    if result.successful():
        result_payload = result.result or {}
        if isinstance(result_payload, dict) and result_payload.get("pdf_public_url"):
            payload["pdf_url"] = result_payload["pdf_public_url"]
        payload["state"] = "SUCCESS"
    elif result.failed():
        payload["state"] = "FAILURE"
        payload["error"] = str(result.result)
    return payload
