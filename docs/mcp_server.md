# Resume Agent MCP Server

This MCP server exposes the Resume Agent tools (FastMCP) for MCP-aware clients (Claude Desktop, VS Code MCP extensions, etc.). It wraps the LangChain-style tools in `src/myagent/tools.py` and adds a data:// resource for resume assets.

## Prerequisites
- Python 3.12, `uv` installed.
- Create/activate venv: `uv venv && source .venv/bin/activate`.
- Install deps: `uv sync`.
- Copy env: `cp sample.env .env` then fill keys (see below).

## Environment Variables
- LLM keys (required for analysis tools): `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`.
- Data/paths (optional overrides): `RESUME_DATA_DIR`, `RESUME_SUMMARY_PATH` or `RESUME_AGGREGATE_PATH`, `RESUME_JD_DIR`, `LOGS_DIR`, `RESUME_FS_URL`, `JD_FS_URL`.
- S3/R2 output (for PDF uploads): `RESUME_S3_BUCKET_NAME` or `S3_BUCKET_NAME`; `RESUME_S3_PUBLIC_BASE_URL` (required when uploading PDFs); optional `RESUME_S3_ENDPOINT_URL`, `RESUME_S3_REGION`/`AWS_REGION`, `RESUME_S3_KEY_PREFIX`, `RESUME_S3_ADDRESSING_STYLE`, `RESUME_S3_ACCESS_KEY_ID`/`RESUME_S3_ACCESS_KEY`/`S3_ACCESS_KEY_ID`/`AWS_ACCESS_KEY_ID`, `RESUME_S3_SECRET_ACCESS_KEY`/`RESUME_S3_SECRET_KEY`/`S3_SECRET_ACCESS_KEY`/`AWS_SECRET_ACCESS_KEY`.
- LaTeX/XeLaTeX must be installed for PDF compilation.

## Start the server
- Default (stdio):
  ```bash
  uv run python scripts/start_mcp_server.py
  ```
- HTTP transport (for testing):
  ```bash
  uv run python scripts/start_mcp_server.py --transport http --port 8000
  ```
- Direct module entry (equivalent): `uv run python -m myagent.mcp_server --transport stdio|http --port 8000`.
- Logs write to `logs/mcp_server.log` (or `LOGS_DIR` override).

## MCP resources
- Resource: `data://{path}` reads files under the project `data/` (or `RESUME_DATA_DIR` override). Returns text for known text types, bytes otherwise.
- Tool: `list_data_directory(path="")` lists contents relative to the data root.

## Available tools (FastMCP names)
- `list_resume_versions`: list YAML resume versions.
- `load_complete_resume(filename)`: render full resume as Markdown.
- `load_resume_section(module_path)`: fetch a single section.
- `update_resume_section(module_path, new_content)`: write one section (required; server forbids whole-file updates).
- `create_new_version(new_version_name)`: copy base template into a new version.
- `delete_resume_version(version_name)`: remove a non-base resume version.
- `list_modules_in_version(filename)`: list section identifiers in a resume file.
- `summarize_resumes_to_index`: build lightweight `resume_summary.yaml` and return its path/message.
- `read_resume_summary`: read the summary YAML.
- `render_resume_to_latex(version)`: produce LaTeX string.
- `compile_resume_pdf(tex_content, version_name="resume")`: compile via xelatex; uploads PDF/latex assets to configured output filesystem or S3 (requires output FS/S3 config).
- `get_resume_yaml_format`: return schema + example YAML for resumes.

## Client configuration examples
- Claude Desktop (`claude_desktop_config.json` snippet):
  ```json
  {
    "mcpServers": {
      "resume-agent": {
        "command": "uv",
        "args": ["run", "python", "scripts/start_mcp_server.py"]
      }
    }
  }
  ```
- VS Code MCP extension: point the command to `uv run python scripts/start_mcp_server.py` (stdio) or use the HTTP transport URL.

## Typical workflows
1) JD tailoring: `read_jd_file` (from tools layer), `analyze_jd`, `load_resume_section`, edit content, `update_resume_section`, then `render_resume_to_latex` + `compile_resume_pdf`.
2) New version: `create_new_version`, inspect with `list_modules_in_version`, edit via `load_resume_section` → `update_resume_section`.
3) Overview: `list_resume_versions`, `summarize_resumes_to_index`, `read_resume_summary`.

## Development notes
- Server code lives in `src/myagent/mcp_server.py`; it decorates functions from `src/myagent/tools.py` and uses FastMCP.
- When adding tools: implement in `tools.py`, import/wrap in `mcp_server.py`, document here.
- Logging configured at module import; respects `LOGS_DIR` from settings.
- Keep section-level updates only; the server intentionally blocks whole-file YAML replacements except through controlled tools.
- Resume format changes: if you modify the resume storage format, always update `schemas/resume_schema.json` (and sample YAMLs like `data/resumes/we_bible.yaml`) to match. For section ordering/enabling, add a top-level `style:` block with `section_order: [<section ids>]` and `section_disabled: {<id>: true}`; rendering should follow `section_order`, skip disabled sections, append remaining enabled sections in original order, and ignore unknown ids. Add tests covering default behavior, custom order, and disabled sections.

## Troubleshooting
- Missing keys → check `.env` (LLM and S3). `render_resume_to_latex` works without S3, but PDF upload needs bucket + public base URL.
- Data path issues → ensure `data/resumes` exists or set `RESUME_DATA_DIR`.
- LaTeX errors → verify XeLaTeX is installed and templates are present under `templates/`.
- HTTP mode not reachable → confirm port, firewall, and that `--transport http` is set.
- Logs: inspect `logs/mcp_server.log` for stack traces and tool-call traces.
