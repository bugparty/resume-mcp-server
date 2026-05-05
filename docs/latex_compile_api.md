# LaTeX Compile Service API Documentation

## Overview

LaTeX Compile Service provides synchronous and asynchronous ways to compile LaTeX documents into PDFs. It supports multi-file uploads, automatic engine detection, and multi-template compilation.

**Base URL**: `https://latex-compile.k.0x1f0c.dev`

---

## Endpoint Overview

| Endpoint | Method | Description |
|------|------|------|
| `/healthz` | GET | Health check |
| `/v1/compile` | POST | Synchronous compile (returns PDF) |
| `/v1/jobs` | POST | Submit an asynchronous job |
| `/v1/jobs/{job_id}` | GET | Query asynchronous job status |

---

## Core Endpoints

### 1. Health Check

```http
GET /healthz
```

**Response**:
```json
{
  "status": "ok"
}
```

---

### 2. Synchronous Compile - Return PDF

```http
POST /v1/compile
```

Compile LaTeX files synchronously and return the PDF directly.

**Request parameters** (multipart/form-data):

| Field | Type | Required | Description |
|------|------|------|------|
| `files` | File[] | Yes | List of LaTeX source files and asset files |
| `main` | string | No | Path to the main `.tex` file (for example `main.tex` or `src/main.tex`) |
| `engine` | string | No | Compile engine: `xelatex`, `pdflatex`, `lualatex` |
| `job_id` | string | No | Custom job ID |
| `format` | string | No | Return format: `pdf` (default) or `json` |

**Engine auto-detection**:
- Detect automatically from the magic comment in the first 10 lines of file content
- `% !TEX program = xelatex` → xelatex
- `% !TEX program = pdflatex` → pdflatex
- `% !TEX program = lualatex` → lualatex
- Default: `xelatex`

**Response** (format=pdf):
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="output_{job_id}.pdf"`
- Header: `X-Job-Id: {job_id}`

**Response** (format=json):
```json
{
  "job_id": "abc123",
  "status": "success",
  "pdf_base64": "JVBERi0xLjQK..."
}
```

**Examples**:
```bash
# Single-file compile
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@main.tex" \
  -o output.pdf

# Multi-file compile, specify the main file
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@main.tex" \
  -F "files=@chapters/intro.tex;filename=chapters/intro.tex" \
  -F "files=@refs.bib" \
  -F "main=main.tex" \
  -F "engine=xelatex" \
  -o output.pdf

# Return JSON format
curl -X POST "https://latex-compile.k.0x1f0c.dev/v1/compile?format=json" \
  -F "files=@main.tex" \
  | jq '.pdf_base64' | tr -d '"' | base64 -d > output.pdf
```

---

### 3. Submit an Asynchronous Job

```http
POST /v1/jobs
```

Submit an asynchronous compile job. Files are uploaded to S3 and then processed by a Celery worker.

**Request parameters** (multipart/form-data):

| Field | Type | Required | Description |
|------|------|------|------|
| `files` | File[] | Yes | List of LaTeX source files and asset files |
| `main` | string | No | Path to the main `.tex` file |
| `engine` | string | No | Compile engine |
| `job_id` | string | No | Custom job ID |

**Response**:
```json
{
  "job_id": "abc123",
  "status": "queued",
  "poll_url": "/v1/jobs/abc123"
}
```

**Example**:
```bash
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/jobs \
  -F "files=@resume.tex" \
  -F "files=@photo.jpg" \
  | jq '.poll_url'
```

---

### 4. Query Asynchronous Job Status

```http
GET /v1/jobs/{job_id}
```

Query the execution status of an asynchronous job.

**Response**:
```json
{
  "job_id": "abc123",
  "status": "success",
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:05Z",
  "result": {
    "pdf_url": "https://.../resume.pdf"
  },
  "error": null
}
```

**Status values**:
- `queued` - Job has been submitted and is waiting to be processed
- `processing` - Currently compiling
- `success` - Compilation succeeded
- `failed` - Compilation failed
- `unknown` - Unknown status

---

## File Upload Rules

### Main File Detection

When the `main` parameter is not specified, detection happens in the following order:
1. If there is only one `.tex` file, use that file
2. Look for `main.tex`
3. Look for `resume.tex`
4. If none are found, return an error

### Subdirectory Support

Files with subdirectory structure are supported:
```bash
curl -X POST /v1/compile \
  -F "files=@main.tex;filename=main.tex" \
  -F "files=@intro.tex;filename=chapters/intro.tex" \
  -F "main=main.tex"
```

### Path Traversal Protection

Requests whose filenames contain `..` are rejected:
```
400 Bad Request: Invalid filename: ../../etc/passwd
```

---

## Error Handling

### HTTP Status Codes

| Status Code | Meaning |
|--------|------|
| 200 | Success |
| 400 | Bad request (missing files, main file not found, etc.) |
| 500 | Compile error (LaTeX syntax errors, etc.) |
| 503 | Celery worker unavailable |

### Error Response Example

```json
{
  "detail": "Main file 'main.tex' not found among uploaded files."
}
```

---

## Use Cases

### Scenario 1: Simple Resume Compile
```bash
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@resume.tex" \
  -o resume.pdf
```

### Scenario 2: Complex Project Compile
```bash
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@thesis.tex;filename=thesis.tex" \
  -F "files=@ch1.tex;filename=chapters/ch1.tex" \
  -F "files=@ch2.tex;filename=chapters/ch2.tex" \
  -F "files=@refs.bib" \
  -F "main=thesis.tex" \
  -F "engine=pdflatex" \
  -o thesis.pdf
```

### Scenario 3: Asynchronous Batch Processing
```bash
# Submit job
JOB=$(curl -s -X POST https://latex-compile.k.0x1f0c.dev/v1/jobs \
  -F "files=@batch_resume.tex" \
  | jq -r '.job_id')

# Poll status
while true; do
  STATUS=$(curl -s https://latex-compile.k.0x1f0c.dev/v1/jobs/$JOB | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "success" ] && break
  sleep 2
done
```

---

## Version Information

- **API Version**: 3.0.0
- **LaTeX Engines**: xelatex (default), pdflatex, lualatex
- **CJK Support**: Yes (supports Chinese, Japanese, and Korean)
