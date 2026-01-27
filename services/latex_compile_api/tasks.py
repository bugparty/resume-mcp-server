from __future__ import annotations

import subprocess
import tempfile
import zipfile
from pathlib import Path

from celery_app import celery_app
from s3_utils import download_s3_object_to_file, upload_bytes_to_s3

LATEX_COMPILE_TASK_NAME = "latex_compile_api.tasks.compile_latex_task"


def _compile_tex(tex_path: Path) -> None:
    subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_path.name,
        ],
        cwd=tex_path.parent,
        check=True,
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

        _compile_tex(tex_path)

        pdf_path = tex_path.with_suffix(".pdf")
        pdf_bytes = pdf_path.read_bytes()

        pdf_public_url, _ = upload_bytes_to_s3(
            pdf_bytes,
            output_filename,
            "application/pdf",
            "resume PDF",
        )

    return {"job_id": job_id, "pdf_public_url": pdf_public_url}
