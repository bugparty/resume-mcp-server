---
name: resume-mcp-safe-json
description: Use when importing resume JSON through MCP fails due to escaping/encoding corruption (for example double-escaped quotes and backslashes). Runs a local safe-import command that normalizes JSON first, then writes section-by-section to the remote resume MCP over SSE.
---

# Resume MCP Safe JSON Import

Use this skill when a resume JSON payload is likely being damaged by transit encoding, not by payload size.

This skill avoids inline JSON args and imports from raw bytes (`file`, `stdin`, or `base64`), then:
- normalizes JSON safely,
- detects double-encoded JSON,
- reports precise parse errors (`line`, `column`, snippet),
- calls remote MCP over SSE and updates resume section-by-section.

## Remote MCP

- Fixed endpoint: `https://resume-mcp.k.0x1f0c.dev/sse`
- Transport: SSE (`/sse` + `/messages/?session_id=...`)

## Command

```bash
python "<path-to-skill>/scripts/safe_resume_import.py" \
  --version "<resume_version>" \
  --input-file "/absolute/path/resume.json"
```

Other input modes:

```bash
# Raw bytes from stdin
cat /absolute/path/resume.json | python "<path-to-skill>/scripts/safe_resume_import.py" --version "<resume_version>" --stdin

# Base64 payload
python "<path-to-skill>/scripts/safe_resume_import.py" --version "<resume_version>" --input-b64 "<BASE64>"
```

Dry run:

```bash
python "<path-to-skill>/scripts/safe_resume_import.py" \
  --version "<resume_version>" \
  --input-file "/absolute/path/resume.json" \
  --dry-run
```

## Input Rules

- Prefer `--input-file`.
- Do not pass inline JSON argument strings like `--json '{...}'`.
- Accepted source JSON shapes:
  - canonical `{ "metadata": ..., "sections": [...] }`
  - top-level section keys like `header`, `summary`, `skills`, `experience`, `projects`, `education`, `custom`/`raw`
