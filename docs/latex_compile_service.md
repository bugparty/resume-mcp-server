# LaTeX 编译服务拆分方案

本文档描述将简历渲染与 LaTeX 编译拆分为独立服务的实现方案，遵循以下约束：
- Broker 使用 Redis
- 结果 PDF 存储在 S3
- 编译产物（中间文件）不保留
- Jinja 渲染与编译服务解耦
- `resume.tex` 不对外回传

## 组件与职责

### Render Service（Jinja/渲染服务）
- 输入：resume 版本号或 YAML
- 行为：生成 `resume.tex`，打包 assets（模板、字体、类文件、图片）
- 输出：将 `resume.tex` 和 `assets.zip` 上传 S3（仅内部使用）

### Compile Service（Celery Worker）
- 输入：S3 object keys（`resume.tex`、`assets.zip`）
- 行为：下载 → 解压 → `xelatex` 编译
- 输出：仅上传 `resume.pdf` 至 S3

### API/Orchestrator
- 输入：对外提交版本号
- 行为：触发 Render、提交 Celery 任务、查询状态
- 输出：仅返回 `job_id` / `task_id` 与最终 PDF URL

## 数据流（简版）
1. API 触发 Render Service：生成 `resume.tex` + `assets.zip` → 上传 S3
2. API 投递 Celery 任务（只传 S3 keys）
3. Worker 拉取文件 → 编译 → 上传 PDF
4. API 查询任务状态 → 返回 PDF URL

## S3 路径约定
默认前缀由 `RESUME_S3_KEY_PREFIX` 控制，job 路径由 `RESUME_PDF_JOB_PREFIX` 控制：

```
s3://<bucket>/<key_prefix>/<job_prefix>/<job_id>/
  - resume.tex
  - assets.zip
  - resume.pdf
```

## assets.zip 内容
assets 包必须包含编译所需全部资源，建议结构：

```
assets/
  awesome-cv.cls
  fonts/...
  latex/
    resume_main.tex.j2
    sections/*.tex.j2
  profile.png
```

## 任务输入/输出

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

## 超时/重试建议
- `CELERY_TASK_TIME_LIMIT`：120s
- `CELERY_TASK_SOFT_TIME_LIMIT`：90s
- `max_retries=2`，`retry_backoff=True`

## 对外工具
新增 MCP 工具：
- `SubmitResumePDFJob`：提交 render+compile 任务
- `GetResumePDFJobStatus`：查询任务状态及 PDF URL

## 独立 REST API（编译服务）

服务目录：`services/latex_compile_api/`

- `POST /v1/compile`：提交编译任务
- `GET /v1/jobs/{task_id}`：查询任务状态与 PDF URL

示例请求：
```
POST /v1/compile
{
  "latex_object_key": "resumes/resume-jobs/<job_id>/resume.tex",
  "assets_object_key": "resumes/resume-jobs/<job_id>/assets.zip",
  "output_filename": "resume-jobs/<job_id>/resume.pdf"
}
```

示例响应：
```
{
  "job_id": "<job_id>",
  "task_id": "<task_id>",
  "status": "queued",
  "output_filename": "resume-jobs/<job_id>/resume.pdf"
}
```

## 运行示例（开发）
```
celery -A myagent.latex_worker worker -Q default
```

