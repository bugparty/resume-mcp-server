# Docker Quick Start Guide

This project provides a ready-to-use Docker image with entry scripts. After container startup, it will:
- Install and prepare Python dependencies, TeX Live (including `xelatex`) and `cloudflared`
- Start MCP HTTP service (default `0.0.0.0:8000`)
- Automatically create Cloudflare temporary tunnel and print public URL `https://*.trycloudflare.com/mcp` for easy use in ChatGPT MCP settings

## Prerequisites

- Docker installed (recommend latest version)
- Internet access (for pulling dependencies and creating tunnels)
- Optional: Prepare `.env` in project root (refer to `sample.env`)

## Build Image

Execute in project root:
```bash
docker build -t resume-mcp:latest .
```

For Apple/ARM if encountering cloudflared architecture issues, try:
```bash
docker buildx build --platform linux/amd64 -t resume-mcp:latest .
```

## Run Container

Simplest run (automatically create temporary tunnel and print public URL):
```bash
docker run --rm -p 8000:8000 resume-mcp:latest
```

Recommended (mount data and template directories, inject local `.env`):
```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/templates:/app/templates" \
  --env-file ./.env \
  resume-mcp:latest
```

Startup log example:
```text
Cloudflare Tunnel Ready: https://xxxxx.trycloudflare.com/mcp
Starting MCP server (HTTP) on 0.0.0.0:8000...
```

Copy `https://xxxxx.trycloudflare.com/mcp` to ChatGPT MCP server configuration.

> Note: Port 8000 is also mapped for local testing via `curl http://localhost:8000/health`; use Cloudflare URL for external access.

## Environment Variables

- Copy `sample.env` to `.env` and fill in required keys (like `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, etc.)
- Inject via `--env-file ./.env`

## Common Verification

Local health check:
```bash
curl http://localhost:8000/health
```

Tunnel health check (replace with your URL):
```bash
curl https://xxxxx.trycloudflare.com/health
```

## Directories and Persistence

- `data/`: Resume YAML files, output PDFs (e.g., `data/resumes/output/`)
- `templates/`: LaTeX template resources

## ChatGPT MCP Configuration Guide

- Server address: `https://*.trycloudflare.com` printed in logs
- Protocol: HTTP/HTTPS
- Authentication: None

## Troubleshooting

- Can't see tunnel URL:
  - Check if container logs show `Cloudflare Tunnel Ready`
  - Container tunnel logs: `/tmp/cloudflared.log`
- Port in use:
  - Adjust `-p 8000:8000` mapping or release host port
- ARM/Apple Silicon:
  - Use `--platform linux/amd64` to rebuild

## Advanced Usage

Background run:
```bash
docker run -d --name resume-mcp -p 8000:8000 resume-mcp:latest
# View logs
docker logs -f resume-mcp
```

Custom external port (container still listens on 8000):
```bash
docker run --rm -p 18000:8000 resume-mcp:latest
```
