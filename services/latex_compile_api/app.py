from __future__ import annotations

import os
import uuid
from typing import Optional

from celery.result import AsyncResult
from fastapi import FastAPI
from pydantic import BaseModel, Field

from celery_app import celery_app
from tasks import LATEX_COMPILE_TASK_NAME

app = FastAPI(title="LaTeX Compile Service", version="1.0.0")


class CompileRequest(BaseModel):
    latex_object_key: str = Field(..., description="S3 object key for resume.tex")
    assets_object_key: str = Field(..., description="S3 object key for assets.zip")
    output_filename: Optional[str] = Field(
        default=None,
        description="Output PDF filename relative to RESUME_S3_KEY_PREFIX",
    )
    job_id: Optional[str] = Field(default=None, description="Optional job id")


class CompileResponse(BaseModel):
    job_id: str
    task_id: str
    status: str
    output_filename: str


class JobStatusResponse(BaseModel):
    task_id: str
    state: str
    pdf_url: Optional[str] = None
    error: Optional[str] = None


def _get_job_prefix() -> str:
    prefix = os.getenv("RESUME_PDF_JOB_PREFIX", "resume-jobs/")
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


def _build_output_filename(job_id: str) -> str:
    job_prefix = _get_job_prefix()
    return f"{job_prefix}{job_id}/resume.pdf"


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/compile", response_model=CompileResponse)
def compile_latex(request: CompileRequest) -> CompileResponse:
    job_id = request.job_id or uuid.uuid4().hex
    output_filename = request.output_filename or _build_output_filename(job_id)

    async_result = celery_app.send_task(
        LATEX_COMPILE_TASK_NAME,
        kwargs={
            "job_id": job_id,
            "latex_object_key": request.latex_object_key,
            "assets_object_key": request.assets_object_key,
            "output_filename": output_filename,
        },
    )

    return CompileResponse(
        job_id=job_id,
        task_id=async_result.id,
        status="queued",
        output_filename=output_filename,
    )


@app.get("/v1/jobs/{task_id}", response_model=JobStatusResponse)
def get_job_status(task_id: str) -> JobStatusResponse:
    result = AsyncResult(task_id, app=celery_app)
    payload = JobStatusResponse(task_id=task_id, state=result.state)
    if result.successful():
        result_payload = result.result or {}
        if isinstance(result_payload, dict) and result_payload.get("pdf_public_url"):
            payload.pdf_url = result_payload["pdf_public_url"]
        payload.state = "SUCCESS"
    elif result.failed():
        payload.state = "FAILURE"
        payload.error = str(result.result)
    return payload
