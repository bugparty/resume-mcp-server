# LaTeX Compile Service API 文档

## 概述

LaTeX Compile Service 提供同步和异步两种方式来编译 LaTeX 文档为 PDF。支持多文件上传、自动引擎检测和多模板编译。

**Base URL**: `https://latex-compile.k.0x1f0c.dev`

---

## 端点总览

| 端点 | 方法 | 描述 |
|------|------|------|
| `/healthz` | GET | 健康检查 |
| `/v1/compile` | POST | 同步编译 (返回 PDF) |
| `/v1/jobs` | POST | 异步提交任务 |
| `/v1/jobs/{job_id}` | GET | 查询异步任务状态 |

---

## 核心端点

### 1. 健康检查

```http
GET /healthz
```

**响应**:
```json
{
  "status": "ok"
}
```

---

### 2. 同步编译 - 返回 PDF

```http
POST /v1/compile
```

同步编译 LaTeX 文件，直接返回 PDF 文件。

**请求参数** (multipart/form-data):

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `files` | File[] | 是 | LaTeX 源文件和资源文件列表 |
| `main` | string | 否 | 主 .tex 文件路径 (如 `main.tex` 或 `src/main.tex`) |
| `engine` | string | 否 | 编译引擎: `xelatex`, `pdflatex`, `lualatex` |
| `job_id` | string | 否 | 自定义任务 ID |
| `format` | string | 否 | 返回格式: `pdf` (默认) 或 `json` |

**Engine 自动检测**:
- 从文件内容前 10 行的 magic comment 自动检测
- `% !TEX program = xelatex` → xelatex
- `% !TEX program = pdflatex` → pdflatex
- `% !TEX program = lualatex` → lualatex
- 默认: `xelatex`

**响应** (format=pdf):
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="output_{job_id}.pdf"`
- Header: `X-Job-Id: {job_id}`

**响应** (format=json):
```json
{
  "job_id": "abc123",
  "status": "success",
  "pdf_base64": "JVBERi0xLjQK..."
}
```

**示例**:
```bash
# 单文件编译
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@main.tex" \
  -o output.pdf

# 多文件编译，指定主文件
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@main.tex" \
  -F "files=@chapters/intro.tex;filename=chapters/intro.tex" \
  -F "files=@refs.bib" \
  -F "main=main.tex" \
  -F "engine=xelatex" \
  -o output.pdf

# 返回 JSON 格式
curl -X POST "https://latex-compile.k.0x1f0c.dev/v1/compile?format=json" \
  -F "files=@main.tex" \
  | jq '.pdf_base64' | tr -d '"' | base64 -d > output.pdf
```

---

### 3. 异步提交任务

```http
POST /v1/jobs
```

提交异步编译任务，文件上传到 S3 后由 Celery Worker 处理。

**请求参数** (multipart/form-data):

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `files` | File[] | 是 | LaTeX 源文件和资源文件列表 |
| `main` | string | 否 | 主 .tex 文件路径 |
| `engine` | string | 否 | 编译引擎 |
| `job_id` | string | 否 | 自定义任务 ID |

**响应**:
```json
{
  "job_id": "abc123",
  "status": "queued",
  "poll_url": "/v1/jobs/abc123"
}
```

**示例**:
```bash
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/jobs \
  -F "files=@resume.tex" \
  -F "files=@photo.jpg" \
  | jq '.poll_url'
```

---

### 4. 查询异步任务状态

```http
GET /v1/jobs/{job_id}
```

查询异步任务的执行状态。

**响应**:
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

**状态值**:
- `queued` - 任务已提交，等待处理
- `processing` - 正在编译
- `success` - 编译成功
- `failed` - 编译失败
- `unknown` - 未知状态

---

## 文件上传规则

### 主文件检测

当未指定 `main` 参数时，按以下顺序检测:
1. 如果只有一个 `.tex` 文件，使用该文件
2. 查找 `main.tex`
3. 查找 `resume.tex`
4. 失败，返回错误

### 子目录支持

支持上传带子目录结构的文件:
```bash
curl -X POST /v1/compile \
  -F "files=@main.tex;filename=main.tex" \
  -F "files=@intro.tex;filename=chapters/intro.tex" \
  -F "main=main.tex"
```

### 路径遍历保护

文件名包含 `..` 的请求会被拒绝:
```
400 Bad Request: Invalid filename: ../../etc/passwd
```

---

## 错误处理

### HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 (文件缺失、主文件未找到等) |
| 500 | 编译错误 (LaTeX 语法错误等) |
| 503 | Celery Worker 不可用 |

### 错误响应示例

```json
{
  "detail": "Main file 'main.tex' not found among uploaded files."
}
```

---

## 使用场景

### 场景 1: 简单简历编译
```bash
curl -X POST https://latex-compile.k.0x1f0c.dev/v1/compile \
  -F "files=@resume.tex" \
  -o resume.pdf
```

### 场景 2: 复杂项目编译
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

### 场景 3: 异步批量处理
```bash
# 提交任务
JOB=$(curl -s -X POST https://latex-compile.k.0x1f0c.dev/v1/jobs \
  -F "files=@batch_resume.tex" \
  | jq -r '.job_id')

# 轮询状态
while true; do
  STATUS=$(curl -s https://latex-compile.k.0x1f0c.dev/v1/jobs/$JOB | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "success" ] && break
  sleep 2
done
```

---

## 版本信息

- **API Version**: 3.0.0
- **LaTeX Engines**: xelatex (default), pdflatex, lualatex
- **CJK Support**: 是 (支持中文、日文、韩文)
