# Docker Quick Start Guide

This project provides a ready-to-use Docker image with entry scripts. After container startup, it will:
- Install and prepare Python dependencies
- Start MCP HTTP service (default `0.0.0.0:8000`)

## Prerequisites

- Docker installed (recommend latest version)
- Internet access (for pulling dependencies)
- Optional: Prepare `.env` in project root (refer to `sample.env`)

## Build Image

Execute in project root:
```bash
docker build -t resume-mcp:latest .
```

For Apple/ARM compatibility, you can build amd64 image:
```bash
docker buildx build --platform linux/amd64 -t resume-mcp:latest .
```

## Run Container

Simplest run:
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
Starting MCP server (HTTP) on 0.0.0.0:8000...
```

Use `http://localhost:8000/mcp` as MCP endpoint when running locally.

## Environment Variables

- Copy `sample.env` to `.env` and fill in required keys (like `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, etc.)
- Inject via `--env-file ./.env`

## Common Verification

Local health check:
```bash
curl http://localhost:8000/health
```

## Directories and Persistence

- `data/`: Resume YAML files, output PDFs (e.g., `data/resumes/output/`)
- `templates/`: LaTeX template resources

## Troubleshooting

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
