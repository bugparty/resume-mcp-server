from __future__ import annotations

import os
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="LaTeX Compile Service", version="2.0.0")


class CompileResponse(BaseModel):
    job_id: str
    status: str
    message: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _compile_tex(tex_path: Path) -> None:
    """Run xelatex to compile the tex file."""
    result = subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_path.name,
        ],
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Extract relevant error from log
        error_msg = result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        raise RuntimeError(f"LaTeX compilation failed:\n{error_msg}")


def _save_uploaded_files(
    files: List[UploadFile], tmp_path: Path, main_file: Optional[str]
) -> Path:
    """
    Save uploaded files to tmp_path and return the path to the main .tex file.
    """
    saved_files = []
    for file in files:
        if not file.filename:
            continue
        
        # Sanitize filename handling (basic)
        # We allow subdirectories if the client sends them (e.g. "chapter/intro.tex")
        # but we must ensure we don't escape tmp_path.
        safe_filename = file.filename.lstrip("/")
        if ".." in safe_filename: 
             # Simple protection against traversal. 
             # For a robust internal tool, we might assume trusted input, but good to be safe.
             raise HTTPException(status_code=400, detail=f"Invalid filename: {file.filename}")
             
        dest_path = tmp_path / safe_filename
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = file.file.read()
        dest_path.write_bytes(content)
        saved_files.append(dest_path)

    if main_file:
        tex_path = tmp_path / main_file
        if not tex_path.exists():
             raise HTTPException(status_code=400, detail=f"Main file '{main_file}' not found among uploaded files.")
        return tex_path
    
    # Heuristics if main_file not provided
    tex_files = [f for f in saved_files if f.suffix.lower() == ".tex"]
    
    if len(tex_files) == 1:
        return tex_files[0]
    
    # Update to support resume.tex default for backward compatibility contexts if needed,
    # or look for "main.tex" or "resume.tex"
    potential_mains = ["main.tex", "resume.tex"]
    for pm in potential_mains:
        p = tmp_path / pm
        if p.exists():
            return p
            
    raise HTTPException(
        status_code=400, 
        detail="Could not determine main .tex file. Please specify 'main_file' or upload exactly one .tex file."
    )


@app.post("/v1/compile")
async def compile_latex(
    files: List[UploadFile] = File(None, description="List of files to upload"),
    main_file: Optional[str] = Form(None, description="The main .tex file to compile (e.g. 'main.tex')"),
    latex_file: Optional[UploadFile] = File(None, description="Legacy: The .tex file"),
    assets_zip: Optional[UploadFile] = File(None, description="Legacy: ZIP archive"),
    job_id: Optional[str] = None,
) -> Response:
    """
    Compile a LaTeX file to PDF.
    
    Supports two modes:
    1. Multi-file upload (Recommended): Upload all source files in `files`.
    2. Legacy mode: `latex_file` + optional `assets_zip`.
    """
    job_id = job_id or uuid.uuid4().hex

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tex_path = None

        # Mode 1: List of files
        if files:
            tex_path = _save_uploaded_files(files, tmp_path, main_file)
        
        # Mode 2: Legacy
        elif latex_file:
            tex_path = tmp_path / "resume.tex"
            tex_content = await latex_file.read()
            tex_path.write_bytes(tex_content)
            
            if assets_zip:
                assets_zip_path = tmp_path / "assets.zip"
                assets_content = await assets_zip.read()
                assets_zip_path.write_bytes(assets_content)
                try:
                    with zipfile.ZipFile(assets_zip_path, "r") as zip_handle:
                        zip_handle.extractall(tmp_path)
                except zipfile.BadZipFile as e:
                     raise HTTPException(status_code=400, detail=f"Invalid assets ZIP file: {e}")
        else:
             raise HTTPException(status_code=400, detail="No files provided. Send 'files' or 'latex_file'.")

        # Compile
        try:
            _compile_tex(tex_path)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        # Read and return PDF
        pdf_path = tex_path.with_suffix(".pdf")
        if not pdf_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Compilation appeared to succeed but no PDF was generated",
            )

        pdf_bytes = pdf_path.read_bytes()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resume_{job_id}.pdf"',
            "X-Job-Id": job_id,
        },
    )


@app.post("/v1/compile/json", response_model=CompileResponse)
async def compile_latex_json(
    files: List[UploadFile] = File(None, description="List of files to upload"),
    main_file: Optional[str] = Form(None, description="The main .tex file to compile"),
    latex_file: Optional[UploadFile] = File(None, description="Legacy: The .tex file"),
    assets_zip: Optional[UploadFile] = File(None, description="Legacy: ZIP archive"),
    job_id: Optional[str] = None,
) -> CompileResponse:
    """
    Compile LaTeX and return JSON status.
    """
    job_id = job_id or uuid.uuid4().hex

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tex_path = None
        
        try:
            if files:
                tex_path = _save_uploaded_files(files, tmp_path, main_file)
            elif latex_file:
                 tex_path = tmp_path / "resume.tex"
                 tex_content = await latex_file.read()
                 tex_path.write_bytes(tex_content)
                 
                 if assets_zip:
                     assets_zip_path = tmp_path / "assets.zip"
                     assets_content = await assets_zip.read()
                     assets_zip_path.write_bytes(assets_content)
                     try:
                         with zipfile.ZipFile(assets_zip_path, "r") as zip_handle:
                             zip_handle.extractall(tmp_path)
                     except zipfile.BadZipFile as e:
                         return CompileResponse(job_id=job_id, status="error", message=f"Invalid ZIP: {e}")
            else:
                 return CompileResponse(job_id=job_id, status="error", message="No files uploaded")

            _compile_tex(tex_path)
            
            pdf_path = tex_path.with_suffix(".pdf")
            if not pdf_path.exists():
                 return CompileResponse(job_id=job_id, status="error", message="No PDF generated")
                 
        except Exception as e:
            return CompileResponse(job_id=job_id, status="error", message=str(e))

    return CompileResponse(
        job_id=job_id,
        status="success",
        message="PDF compiled successfully",
    )
