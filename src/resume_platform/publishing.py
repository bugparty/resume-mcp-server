"""Turning a resume version into deliverables: a compiled PDF, or an Overleaf
project archive. Both are saved to the output filesystem and can optionally
be uploaded to S3-compatible storage.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from fs.copy import copy_fs
from fs.osfs import OSFS

from resume_platform.infrastructure.filesystem import get_output_fs
from resume_platform.infrastructure.s3_utils import upload_bytes_to_s3
from resume_platform.paths import LATEX_ASSET_DIRS, LATEX_ASSET_FILES, TEMPLATES_DIR
from resume_platform.resume.repository import validate_version_name
from resume_platform.resume_renderer import compile_tex_remote, render_resume

OUTPUT_URI_PREFIX = "data://resumes/output/"
MAIN_TEX = "main.tex"


@dataclass(frozen=True)
class Artifact:
    filename: str
    content: bytes
    uri: str
    latex_assets_uri: str


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def stage_latex_project(latex: str, directory: Path, tex_name: str = MAIN_TEX) -> Path:
    """Write ``latex`` plus the class file and fonts it needs into ``directory``."""
    tex_path = directory / tex_name
    tex_path.write_text(latex, encoding="utf-8")
    for name in LATEX_ASSET_FILES:
        if (TEMPLATES_DIR / name).exists():
            shutil.copy(TEMPLATES_DIR / name, directory / name)
    for name in LATEX_ASSET_DIRS:
        if (TEMPLATES_DIR / name).is_dir():
            shutil.copytree(TEMPLATES_DIR / name, directory / name)
    return tex_path


def _export_directory(source: Path, name: str) -> str:
    """Copy a local directory into the output filesystem; return its URI."""
    output_fs = get_output_fs()
    if output_fs.exists(name):
        output_fs.removetree(name)
    target = output_fs.makedir(name, recreate=True)
    try:
        with OSFS(str(source)) as source_fs:
            copy_fs(source_fs, target)
    finally:
        target.close()
    return OUTPUT_URI_PREFIX + name


def _zip_directory(directory: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(directory).as_posix())
    return buffer.getvalue()


def build_pdf(version_name: str) -> Artifact:
    """Render and compile a version; save PDF + LaTeX sources to output storage."""
    version_name = validate_version_name(version_name)
    latex = render_resume(version_name)
    stem = f"{version_name}_{_timestamp()}"
    filename = f"{stem}.pdf"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_path = stage_latex_project(latex, tmp_path)
        pdf_path = compile_tex_remote(tex_path)
        pdf_bytes = Path(pdf_path).read_bytes()
        Path(pdf_path).unlink(missing_ok=True)
        assets_uri = _export_directory(tmp_path, f"{stem}_latex")

    get_output_fs().writebytes(filename, pdf_bytes)
    return Artifact(filename, pdf_bytes, OUTPUT_URI_PREFIX + filename, assets_uri)


def build_overleaf_package(version_name: str) -> Artifact:
    """Render a version to an uncompiled LaTeX project zipped for Overleaf."""
    version_name = validate_version_name(version_name)
    latex = render_resume(version_name)
    stem = f"{version_name}_{_timestamp()}"
    filename = f"{stem}_overleaf.zip"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        stage_latex_project(latex, tmp_path)
        zip_bytes = _zip_directory(tmp_path)
        assets_uri = _export_directory(tmp_path, f"{stem}_latex")

    get_output_fs().writebytes(filename, zip_bytes)
    return Artifact(filename, zip_bytes, OUTPUT_URI_PREFIX + filename, assets_uri)


def publish_pdf(version_name: str) -> dict[str, str]:
    artifact = build_pdf(version_name)
    public_url, _ = upload_bytes_to_s3(
        artifact.content, artifact.filename, "application/pdf", "resume PDF"
    )
    return {
        "public_url": public_url,
        "filename": artifact.filename,
        "pdf_path": artifact.uri,
        "latex_assets_dir": artifact.latex_assets_uri,
    }


def publish_overleaf(version_name: str) -> dict[str, str]:
    artifact = build_overleaf_package(version_name)
    public_url, _ = upload_bytes_to_s3(
        artifact.content,
        artifact.filename,
        "application/zip",
        "resume Overleaf package",
    )
    return {
        "overleaf_url": f"https://www.overleaf.com/docs?snip_uri={quote(public_url, safe='')}",
        "public_url": public_url,
        "filename": artifact.filename,
        "zip_path": artifact.uri,
        "latex_assets_dir": artifact.latex_assets_uri,
    }
