# LaTeX Compilation Service Split Plan

This document describes the implementation plan for splitting resume rendering and LaTeX compilation into independent services, following these constraints:
- Broker uses Redis
- Result PDF is stored in S3
- Compilation artifacts (intermediate files) are not retained
- Jinja rendering and compilation service are decoupled
- `resume.tex` is not returned externally

## Components and Responsibilities

### Render Service (Jinja/Rendering Service)
- Input: Resume version number or YAML
- Behavior: Generate `resume.tex`, package assets (templates, fonts, class files, images)
- Output: Upload `resume.tex` and `assets.zip` to S3 (internal use only)

### Compile Service (Celery Worker)
- Input: S3 object keys (`resume.tex`, `assets.zip`)
- Behavior: Download -> Unzip -> `xelatex` compilation
- Output: Upload only `resume.pdf` to S3

### API/Orchestrator
- Input: External submission of version number
- Behavior: Trigger Render, submit Celery task, query status
- Output: Return only `job_id` / `task_id` and final PDF URL

## Data Flow (Simplified)
1. API triggers Render Service: Generate `resume.tex` + `assets.zip` -> Upload to S3
2. API submits Celery task (sends only S3 keys)
3. Worker pulls files -> Compiles -> Uploads PDF
4. API queries task status -> Returns PDF URL

## S3 Path Convention
Default prefix is controlled by `RESUME_S3_KEY_PREFIX`, job path by `RESUME_PDF_JOB_PREFIX`:

```
s3://<bucket>/<key_prefix>/<job_prefix>/<job_id>/
  - resume.tex
  - assets.zip
  - resume.pdf
```

## assets.zip Content
The assets package must contain all resources required for compilation, suggested structure:

```
assets/
  awesome-cv.cls
  fonts/...
  latex/
    resume_main.tex.j2
    sections/*.tex.j2
  profile.png
```

## Task Input/Output

### Task Input
```
{
  "job_id": "uuid",
  "latex_object_key": "resumes/resume-jobs/<job_id>/resume.tex",
  "assets_object_key": "resumes/resume-jobs/<job_id>/assets.zip",
  "output_filename": "resume-jobs/<job_id>/resume.pdf"
}
```

### Task Output
```
{
  "job_id": "uuid",
  "pdf_public_url": "https://public.example/resumes/resume-jobs/<job_id>/resume.pdf"
}
```

## Timeout/Retry Recommendations
- `CELERY_TASK_TIME_LIMIT`: 120s
- `CELERY_TASK_SOFT_TIME_LIMIT`: 90s
- `max_retries=2`, `retry_backoff=True`

## External Tools
Add MCP tools:
- `SubmitResumePDFJob`: Submit render+compile task
- `GetResumePDFJobStatus`: Query task status and PDF URL

## Independent REST API (Compilation Service)

Service directory: `services/latex_compile_api/`

- `POST /v1/compile`: Submit compilation task
- `GET /v1/jobs/{task_id}`: Query task status and PDF URL

Example Request:
```
POST /v1/compile
{
  "latex_object_key": "resumes/resume-jobs/<job_id>/resume.tex",
  "assets_object_key": "resumes/resume-jobs/<job_id>/assets.zip",
  "output_filename": "resume-jobs/<job_id>/resume.pdf"
}
```

Example Response:
```
{
  "job_id": "<job_id>",
  "task_id": "<task_id>",
  "status": "queued",
  "output_filename": "resume-jobs/<job_id>/resume.pdf"
}
```

## Running Example (Development)
```
celery -A myagent.latex_worker worker -Q default
```
