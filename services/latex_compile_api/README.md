# LaTeX Compile REST API

独立 LaTeX 编译服务，提供 REST API 触发编译并查询状态。依赖 Redis 作为 Celery Broker，S3 作为输入/输出存储。

## 运行
```
uvicorn app:app --host 0.0.0.0 --port 8080
```

## Worker
```
uv run celery -A tasks worker -Q default
```

## API
- `POST /v1/compile`
  - 请求：`latex_object_key`、`assets_object_key`、可选 `job_id`、`output_filename`
  - 返回：`task_id`、`job_id`、`output_filename`
- `GET /v1/jobs/{task_id}`
  - 返回：`state`、成功时 `pdf_url`

