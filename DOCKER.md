# Docker 快速使用指南

本项目提供开箱即用的 Docker 镜像与入口脚本。容器启动后会：
- 安装并准备 Python 依赖、TeX Live（含 `xelatex`）与 `cloudflared`
- 启动 MCP HTTP 服务（默认 `0.0.0.0:8000`）
- 自动拉起 Cloudflare 临时隧道并打印 `https://*.trycloudflare.com/mcp` 公网 URL，方便在 ChatGPT 的 MCP 设置中使用

## 前置要求
- 已安装 Docker（建议使用最新版）
- 可访问外网（用于拉取依赖与创建隧道）
- 可选：在项目根目录准备 `.env`（参考 `sample.env`）

## 构建镜像
在项目根目录执行：
```bash
docker build -t resume-mcp:latest .
```
Apple/ARM 如遇 cloudflared 架构问题，可尝试：
```bash
docker buildx build --platform linux/amd64 -t resume-mcp:latest .
```

## 运行容器
最简运行（自动创建临时隧道并打印公网 URL）：
```bash
docker run --rm -p 8000:8000 resume-mcp:latest
```
推荐（挂载数据与模板目录，注入本地 `.env`）：
```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/templates:/app/templates" \
  --env-file ./.env \
  resume-mcp:latest
```
启动日志示例：
```text
Cloudflare Tunnel Ready: https://xxxxx.trycloudflare.com/mcp
Starting MCP server (HTTP) on 0.0.0.0:8000...
```
将 `https://xxxxx.trycloudflare.com/mcp` 复制到 ChatGPT 的 MCP 服务器配置中即可。

> 说明：同时映射了宿主 `8000` 端口，便于本机通过 `curl http://localhost:8000/health` 测试；外网访问请使用 Cloudflare URL。

## 环境变量
- 复制 `sample.env` 为 `.env` 并填入所需的 Key（如 `OPENAI_API_KEY`、`GOOGLE_API_KEY`、`DEEPSEEK_API_KEY` 等）
- 通过 `--env-file ./.env` 注入容器

## 常用验证
本地健康检查：
```bash
curl http://localhost:8000/health
```
隧道健康检查（替换为你的 URL）：
```bash
curl https://xxxxx.trycloudflare.com/health
```

## 目录与持久化
- `data/`：简历 YAML、输出 PDF（如 `data/resumes/output/`）
- `templates/`：LaTeX 模板资源

## ChatGPT MCP 配置指引
- 服务器地址：日志中打印的 `https://*.trycloudflare.com`
- 协议：HTTP/HTTPS
- 认证：无

## 故障排查
- 看不到隧道 URL：
  - 观察容器日志是否出现 `Cloudflare Tunnel Ready`
  - 容器内隧道日志：`/tmp/cloudflared.log`
- 端口占用：
  - 调整 `-p 8000:8000` 映射或释放宿主机端口
- ARM/Apple Silicon：
  - 使用 `--platform linux/amd64` 重新构建

## 进阶
后台运行：
```bash
docker run -d --name resume-mcp -p 8000:8000 resume-mcp:latest
# 查看日志
docker logs -f resume-mcp
```
自定义对外端口（容器仍监听 8000）：
```bash
docker run --rm -p 18000:8000 resume-mcp:latest
```
