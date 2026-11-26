# Resume MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant
(Claude, ChatGPT, any MCP client) manage your resume: keep several tailored
versions, edit them section by section, search your past experience
semantically, and export polished PDFs (LaTeX, awesome-cv) or Overleaf
projects.

Resumes are stored as schema-validated YAML (one file per version). The
assistant edits them through a Markdown text view; every edit is parsed back,
validated, and only then saved.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp sample.env .env          # optional: storage, PDF upload, embedding keys
uv run resume-mcp           # stdio transport, for Claude Desktop / Claude Code
uv run resume-mcp --transport http --port 8000   # HTTP: /mcp and /sse
```

### Connect a client

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "resume": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/resume-mcp-server", "resume-mcp"]
    }
  }
}
```

Claude Code: `claude mcp add resume -- uv run --directory /path/to/resume-mcp-server resume-mcp`

ChatGPT / remote clients: run the HTTP transport and expose it, e.g.
`cloudflared tunnel --url http://localhost:8000`, then use
`https://<tunnel>/mcp` as the server URL. See [docs/deployment.md](docs/deployment.md)
for Docker and Kubernetes.

## Tools

All tools address a resume by `version_name` (e.g. `resume`, without
`.yaml`). Text tools take an optional `section_id` — omit it to work on the
whole resume.

| Area | Tools |
|---|---|
| Versions | `list_resume_versions`, `create_resume_version`, `copy_resume_version`, `delete_resume_version` |
| Reading | `load_complete_resume`, `list_resume_sections`, `read_resume_text` |
| Editing | `replace_resume_text`, `insert_resume_text`, `delete_resume_text`, `update_resume_section` |
| Layout | `get_resume_layout`, `set_section_visibility`, `set_section_order` |
| Search | `search_resume_entries`, `build_vector_index`, `get_vector_index_status` |
| Rendering | `render_resume_pdf`, `render_resume_to_overleaf` |
| Help | `get_resume_yaml_format`, `diagnose_filesystems` |

Full parameter reference: [docs/mcp_tools.md](docs/mcp_tools.md) (generated
from the code).

## Configuration

Everything is optional and set via environment variables (or `.env`); see
the commented [sample.env](sample.env). The main knobs:

- **Storage** — `RESUME_DATA_DIR` / `RESUME_JD_DIR` (default `data/resumes`,
  `data/jd`), or `RESUME_FS_URL` / `JD_FS_URL` for any PyFilesystem2 URL such
  as `s3://bucket/prefix`.
- **PDF export** — `LATEX_COMPILE_API_URL` (the external
  [LaTeX compile service](docs/latex_compile_api.md)) and `RESUME_S3_*` for
  uploading the result.
- **Semantic search** — `EMBEDDING_PROVIDER` plus `GOOGLE_API_KEY` or
  `OPENAI_API_KEY`.

In HTTP mode, `GET /health` is a liveness probe and `GET /error-logs`
(`?tool_name=&failure_kind=&limit=&offset=`) lists recent failed tool calls.

## Development

```bash
./run_tests.sh                       # full suite + coverage (what CI runs)
./run_tests.sh -k layout             # extra args go to pytest
uv run black src tests scripts       # formatting (CI runs black --check)
uv run python scripts/generate_mcp_docs.py   # after changing any tool
```

Tests run every tool through a real in-memory MCP client against a private
copy of `tests/fixtures/test_data`, so they never touch your data. See
[docs/architecture.md](docs/architecture.md) for the code layout and how to
add a tool.

Other scripts in `scripts/`: `render_resume_cli.py` (render/compile from the
command line), `validate_resume_yaml.py`, `convert_latex_resumes.py`
(import old LaTeX resumes), `summarize_resumes.py`, and log viewers.
