# AGENTS GUIDE (keep ~150 lines)

## Quick Start
- From repo root, create/activate env: `uv venv && source .venv/bin/activate` (Python 3.12). Cursor rule also says `cd /home/bowman/myagent && source .venv/bin/activate`; prefer repo root but honor that if Cursor shells are pinned there.
- Install deps: `uv sync` (locked) or `uv pip install -r requirement.txt` (production mirror).
- Run the CLI agent: `uv run python main.py [--data-dir DATA_DIR --aggregate-path AGG_PATH]`.
- Core layout: `src/myagent/` code; `data/` assets ( `jd/`); `templates/` mail-merge and LaTeX; tests under `tests/` and `tests/e2e/`.

## Build / Lint / Test
- Full test suite: `uv run python scripts/run_all_tests.py` (schema + pytest + integrations) or `uv run pytest`.
- Coverage: `uv run pytest --cov`.
- Single test file: `uv run pytest tests/path/to/test_file.py`.
- Single test node: `uv run pytest tests/path/to/test_file.py -k test_name`.
- Smoke e2e: `uv run pytest tests/e2e/test_agent2.py`.
- Reproduce CI batch without uv: `python tests/run_all_tests.py`.
- Format: `uv run black .` (88 cols, trailing commas, 4-space indents).
- No dedicated linter config found; follow Black + repo style and keep imports tidy.

## Repo Structure Notes
- Entrypoint: `main.py` wires agent flows; helpers live in `src/myagent/tools.py`, `resume_loader.py`, `resume_renderer.py`, `resume_input_parser.py`, `filesystem.py`, `settings.py`, `llm_config.py`, `mcp_server.py`, and `models/`.
- Data roots default to `data/resumes`, summaries under `src/myagent/resume_summary.yaml`, JDs under `data/jd`, logs under `logs` (fallbacks under `/tmp/resume_mcp/...` if unwritable).
- Templates: LaTeX assets under `templates/` and `templates/latex`; resume template `templates/resume_template.tex`.

## Environment & Secrets
- Copy `sample.env` to `.env`; required: `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`. Optional overrides: `RESUME_DATA_DIR`, `RESUME_SUMMARY_PATH` (or `RESUME_AGGREGATE_PATH`), `RESUME_JD_DIR`, `LOGS_DIR`, `DEEPSEEK_BASE_URL`, filesystem URLs `RESUME_FS_URL` and `JD_FS_URL`.
- Never commit secrets; prefer environment vars for CI. Document new keys in `project_docs.md`.

## Code Style (Python)
- Formatter: Black (88 chars). Keep lines concise; break chains/args rather than exceeding width.
- Imports: stdlib, third-party, local; no unused imports. Prefer explicit over wildcard. Use relative imports within `myagent` when already inside package.
- Typing: prefer `|` unions, annotate public functions, and return concrete types. Use `Optional` only when unavoidable; favour non-nullable paths with validation. Dataclasses (`settings.py`) use explicit field types.
- Naming: modules/functions snake_case, classes PascalCase, constants UPPER_SNAKE_CASE. Filesystem URLs and env keys mirrored in code should stay uppercase.
- Strings: default to double quotes unless single quotes avoid escapes. Keep f-strings for interpolation; avoid `.format` unless needed.
- Collections: avoid mutable defaults; copy inputs if you mutate. When returning dicts for JSON, ensure `ensure_ascii=False` when user-facing (see `tools.list_resume_versions_tool`).
- Errors: do not swallow exceptions; include context. Use narrow `except Exception as exc` only around external I/O/LLM calls; return/log helpful messages (see `analyze_jd_tool`). No bare `except`. Prefer raising explicit `RuntimeError` when required env vars missing (`llm_config._require_env`).
- Logging: use module-level `logger = logging.getLogger(__name__)` (`resume_renderer.py`). Avoid `print`. Prefer structured text that aids debugging. For deprecations, use `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
- Path handling: use `pathlib.Path`; avoid stringly paths. Check writability before use (`settings._is_directory_writable`). Always open files with encoding="utf-8".
- Unicode/LaTeX: preserve replacements in `resume_renderer.py` (`UNICODE_LATEX_TOKENS`, `UNICODE_SIMPLE_REPLACEMENTS`). Do not remove the pre/post-processing helpers; add new tokens carefully.
- LLM clients: lazy singletons in `llm_config.py`. Do not eagerly create clients; use `get_llm`/`get_thinking_llm` with provider string. Keep temperature/top_p consistent unless changing model behaviour intentionally.
- Tools API: keep pydantic models in `tools.py` descriptive with `Field(..., description=...)`. When adding tools, wire via `StructuredTool.from_function` and maintain consistent names/descriptions for agents.
- File systems: prefer the fs abstraction (`get_resume_fs`, `get_jd_fs`, `get_output_fs`) instead of direct disk writes. When copying, use `fs.copy.copy_fs` and close handles.

## Testing Guidance
- Test files named `test_*.py` in `tests/` or `tests/e2e/`. Use pytest style asserts.
- Add coverage for resume parsing/manipulation first (`tests/test_resume_operations.py` suggested location). Mirror layout of new code: unit tests near helpers, e2e for CLI flows.
- Use fixtures in `tests/__init__.py` or `conftest.py` when shared. Avoid global state; reset module-level singletons or use monkeypatch for `_SETTINGS`/LLM caches.
- To iterate quickly: `uv run pytest tests/path -k keyword -vv` and `-s` for printouts (discouraged in code, fine in tests).

## Runtime / CLI Notes
- `load_settings` caches settings; prefer `get_settings()` where possible. If you override paths, pass explicit args to `load_settings` and respect fallback logic.
- Resume operations should flow through `resume_loader.py` helpers to keep format consistent. When creating versions, avoid deleting base `resume` (enforced in `delete_resume_version_tool`).
- Rendering: use `render_resume` then `compile_tex` via `compile_resume_pdf_tool`; copy only essential template assets/fonts. Preserve timestamped output naming and `data://resumes/output/` scheme.
- Input parsing: `resume_input_parser.py` handles CLI args; keep new flags documented in help text.

## Cursor Rules (from .cursorrules)
- Treat the Cursor rule set as authoritative for assistants. Key points mirrored here:
  - Activate venv before Python commands: `cd /home/bowman/myagent && source .venv/bin/activate` (align with repo root if paths differ).
  - Same build/test commands as above: `uv venv && source .venv/bin/activate`, `uv sync`, `uv run python main.py ...`, `uv run python scripts/run_all_tests.py`, `uv run pytest` (or `--cov`), `python tests/run_all_tests.py`.
  - Structure, testing, commit, and environment expectations match this AGENTS guide.

## Git / PR Workflow
- Commit style: imperative, present tense, <72 chars (e.g., "Add memory management..."). Do not amend unless asked. Avoid committing secrets or `.env`.
- PRs must list validation steps (`uv run pytest`, manual notes) and mention schema/config changes explicitly. Include screenshots/sample outputs when resume formats change.
- Respect existing user changes; do not revert. Never run destructive git commands.

## When Adding Code
- Keep agent prompts centralized rather than inline strings to aid reuse/testing.
- Ensure new commands are documented in this file when relevant. Update tests/run_all_tests.py if orchestration changes.
- Prefer functional helpers over duplicating logic; extend existing utilities in `resume_renderer.py`, `resume_loader.py`, and `filesystem.py` where possible.
- Keep user-facing messages concise and actionable; return JSON strings only when consumers expect them.

## Support Checklist
- Env ready (`.venv` active, .env populated).
- Dependencies installed (`uv sync`).
- Run targeted tests for changed areas (`uv run pytest tests/...`).
- Format code (`uv run black .`).
- Update docs/config samples if new env vars or templates are added.
