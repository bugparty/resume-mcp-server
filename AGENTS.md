# AGENTS GUIDE (keep ~150 lines)

## Quick Start
- From repo root, create/activate env: `uv venv && source .venv/bin/activate` (Python 3.12), or just prefix commands with `uv run`.
- Install deps: `uv sync` (locked).
- Run the MCP server: `uv run resume-mcp` (stdio) or `uv run resume-mcp --transport http --port 8000`.
- Core layout: `src/resume_platform/` code; `data/` assets (`resumes/`, `jd/`); `templates/` LaTeX + YAML template; tests under `tests/`. Architecture: `docs/architecture.md`.

## Build / Lint / Test
- Full test suite (exactly what CI runs): `./run_tests.sh` (pytest + coverage; schema validation and MCP contract tests are part of pytest).
- Single test file: `uv run pytest tests/path/to/test_file.py`; single test: add `-k test_name`.
- MCP tool contract: `tests/test_mcp_server.py` (in-memory MCP client, every tool). Tool reference: `uv run python scripts/generate_mcp_docs.py` regenerates `docs/mcp_tools.md`; a test fails if it is stale.
- Lint + format: `uv run ruff check --fix . && uv run ruff format .` (config in `pyproject.toml`, 88 cols); CI runs `ruff check` and `ruff format --check`.

## Repo Structure Notes
- Entrypoint: `resume-mcp` console script -> `interfaces/mcp/server.py:cli`. MCP tools live in `interfaces/mcp/tools.py` (thin functions + `TOOLS` registry); domain logic in `resume/` (`repository`, `versions`, `layout`, `views`, `editing`), plus `publishing.py`, `resume_renderer.py`, `resume_input_parser.py`, `vector_search.py`; infrastructure in `infrastructure/` (`settings`, `filesystem`, `bootstrap`, `s3_utils`, `llm_config`).
- Data roots default to `data/resumes`, JDs under `data/jd`, logs under `logs` (fallbacks under `/tmp/resume_mcp/...` if unwritable).
- Templates: LaTeX templates under `templates/latex`, class/fonts in `templates/`; new versions start from `templates/resume_template.yaml`. Repo paths come from `resume_platform/paths.py` (no `parents[N]`).

## Environment & Secrets
- Copy `sample.env` to `.env`; nothing is required for local use. Embedding keys (`GOOGLE_API_KEY` or `OPENAI_API_KEY`) enable semantic search; `RESUME_S3_*` enable PDF upload. Optional overrides: `RESUME_DATA_DIR`, `RESUME_JD_DIR`, `LOGS_DIR`, filesystem URLs `RESUME_FS_URL` and `JD_FS_URL`, `LATEX_COMPILE_API_URL` (URL of the separately deployed latex-compile-service, default `https://latex-compile.k.0x1f0c.dev`). The latex-compile service lives in its own repo at `latex-compile-service/` (to be extracted) — do not add service code here.
- Never commit secrets; prefer environment vars for CI. Document new keys in `sample.env`.

## Code Style (Python)
- Formatter/linter: Ruff (88 chars, Black-compatible style; import order, pyupgrade, bugbear and no-`print` in `src/` are enforced). Keep lines concise; break chains/args rather than exceeding width.
- Imports: stdlib, third-party, local; no unused imports. Prefer explicit over wildcard. Use relative imports within `resume_platform` subpackages where already used.
- Typing: prefer `|` unions, annotate public functions, and return concrete types. Use `Optional` only when unavoidable; favour non-nullable paths with validation. Dataclasses (`settings.py`) use explicit field types.
- Naming: modules/functions snake_case, classes PascalCase, constants UPPER_SNAKE_CASE. Filesystem URLs and env keys mirrored in code should stay uppercase.
- Strings: default to double quotes unless single quotes avoid escapes. Keep f-strings for interpolation; avoid `.format` unless needed.
- Collections: avoid mutable defaults; copy inputs if you mutate. MCP tools return dicts (FastMCP serialises them); use `ensure_ascii=False` if you ever hand-serialise user-facing JSON.
- Errors: do not swallow exceptions; include context. Use narrow `except Exception as exc` only around external I/O/LLM calls; raise with an actionable message (MCP tools surface it as a tool error). No bare `except`. Prefer raising explicit `RuntimeError` when required env vars missing (`llm_config._require_env`).
- Logging: use module-level `logger = logging.getLogger(__name__)` (`resume_renderer.py`). Avoid `print`. Prefer structured text that aids debugging. For deprecations, use `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
- Path handling: use `pathlib.Path`; avoid stringly paths. Check writability before use (`settings._is_directory_writable`). Always open files with encoding="utf-8".
- Unicode/LaTeX: preserve replacements in `resume_renderer.py` (`UNICODE_LATEX_TOKENS`, `UNICODE_SIMPLE_REPLACEMENTS`). Do not remove the pre/post-processing helpers; add new tokens carefully.
- Embeddings: lazy singletons in `llm_config.get_embedding_model`. The server makes no chat-LLM calls; the MCP client is the LLM.
- MCP tools: follow the conventions at the top of `interfaces/mcp/tools.py` (`version_name` + optional `section_id`, raise on failure, `Annotated[..., Field(description=...)]` params). Steps for adding a tool: `docs/architecture.md`.
- File systems: prefer the fs abstraction (`get_resume_fs`, `get_jd_fs`, `get_output_fs`) instead of direct disk writes. When copying, use `fs.copy.copy_fs` and close handles.

## Testing Guidance
- Test files named `test_*.py` in `tests/` (pytest only collects `tests/`). Use pytest style asserts.
- `tests/conftest.py` gives every test a private copy of `tests/fixtures/test_data` and bootstraps the runtime against it; tests may freely create/edit/delete versions. Never write to the repo from tests.
- Fake only network edges (LaTeX compile service, S3, embeddings) with monkeypatch; exercise real rendering/storage otherwise.
- To iterate quickly: `uv run pytest tests/path -k keyword -vv` and `-s` for printouts (discouraged in code, fine in tests).
- **MANDATORY**: Run `./run_tests.sh` after any code modification to verify standard and integration tests pass.

## Runtime / CLI Notes
- Settings resolve lazily via `get_settings()`; runtime state is assembled only by `bootstrap()` (see ADR-0001). Do not add import-time side effects.
- Resume persistence goes through `resume/repository.py` (validates version names). The base `resume` version cannot be deleted (`resume/versions.py`).
- Rendering/export: `publishing.py` (`build_pdf`, `build_overleaf_package`, `publish_*`); it stages only essential template assets/fonts. Preserve timestamped output naming and the `data://resumes/output/` scheme.
- Markdown -> YAML section parsing lives in `resume_input_parser.py`.

## Cursor Rules (from .cursorrules)
- Treat the Cursor rule set as authoritative for assistants. Key points mirrored here:
  - Activate venv before Python commands (or use `uv run`).
  - Same build/test commands as above: `uv sync`, `uv run resume-mcp`, `./run_tests.sh`.
  - Structure, testing, commit, and environment expectations match this AGENTS guide.

## Git / PR Workflow
- Commit style: imperative, present tense, <72 chars (e.g., "Add memory management..."). Do not amend unless asked. Avoid committing secrets or `.env`.
- PRs must list validation steps (`uv run pytest`, manual notes) and mention schema/config changes explicitly. Include screenshots/sample outputs when resume formats change.
- Respect existing user changes; do not revert. Never run destructive git commands.

## When Adding Code
- Keep agent prompts centralized rather than inline strings to aid reuse/testing.
- Ensure new commands are documented in this file when relevant; `run_tests.sh` is the single test entry point.
- Prefer functional helpers over duplicating logic; extend existing utilities in `resume_renderer.py`, `resume_loader.py`, and `filesystem.py` where possible.
- Keep user-facing messages concise and actionable; return JSON strings only when consumers expect them.

## Support Checklist
- Env ready (`.venv` active, .env populated).
- Dependencies installed (`uv sync`).
- Run all tests: `./run_tests.sh`.
- Lint and format (`uv run ruff check --fix . && uv run ruff format .`).
- Update docs/config samples if new env vars or templates are added.
