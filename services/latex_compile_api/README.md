# LaTeX Compile REST API

Independent LaTeX compilation service providing REST API to trigger compilation and query status. Depends on Redis as Celery Broker and S3 as input/output storage.

## Run
```
uvicorn app:app --host 0.0.0.0 --port 8080
```

## Worker
```
uv run celery -A tasks worker -Q default
```

## API
- `POST /v1/compile`
  - Request: `latex_object_key`, `assets_object_key`, optional `job_id`, `output_filename`
  - Response: `task_id`, `job_id`, `output_filename`
- `GET /v1/jobs/{task_id}`
  - Response: `state`, `pdf_url` (on success)
