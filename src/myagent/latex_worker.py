from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from celery import Celery

from .resume_renderer import compile_tex
from .s3_utils import download_s3_object_to_file, upload_bytes_to_s3

LATEX_COMPILE_TASK_NAME = "myagent.latex_worker.compile_latex_task"


def _get_celery_broker_url() -> str:
    return os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")


def _get_celery_result_backend() -> str:
    return os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


celery_app = Celery(
    "latex_worker",
    broker=_get_celery_broker_url(),
    backend=_get_celery_result_backend(),
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "120")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "90")),
)


@celery_app.task(
    name=LATEX_COMPILE_TASK_NAME,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def compile_latex_task(
    self,
    job_id: str,
    latex_object_key: str,
    assets_object_key: str,
    output_filename: str,
) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tex_path = tmp_path / "resume.tex"
        assets_zip_path = tmp_path / "assets.zip"

        download_s3_object_to_file(latex_object_key, tex_path, "resume LaTeX")
        download_s3_object_to_file(assets_object_key, assets_zip_path, "resume assets")

        with zipfile.ZipFile(assets_zip_path, "r") as zip_handle:
            zip_handle.extractall(tmp_path)

        compile_tex(tex_path)

        pdf_path = tex_path.with_suffix(".pdf")
        pdf_bytes = pdf_path.read_bytes()

        pdf_public_url, _ = upload_bytes_to_s3(
            pdf_bytes,
            output_filename,
            "application/pdf",
            "resume PDF",
        )

    return {"job_id": job_id, "pdf_public_url": pdf_public_url}
