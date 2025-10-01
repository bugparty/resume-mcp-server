# Repository Guidelines

## Project Structure & Module Organization
- Application sources live under `src/myagent/`; `main.py` wires agent flows, while helpers such as `tools.py`, `resume_loader.py`, and `resume_renderer.py` encapsulate integrations.
- Domain assets live under `data/` (`BowenResume/`, `jd/`) and Mail Merge templates sit in `templates/`.
- Keep configuration samples in `sample.env` and shared settings in `llm_config.py`.
- Automated checks reside in `tests/` (unit/integration) and `tests/e2e/` (smoke tests like `test_agent2.py`); mirror this layout for new suites.

## Build, Test, and Development Commands
- `uv venv && source .venv/bin/activate` creates/activates the local Python 3.12 environment.
- `uv sync` installs locked dependencies from `pyproject.toml` and `uv pip install -r requirement.txt` mirrors production pins when needed.
- `uv run python main.py [--data-dir DATA_DIR --aggregate-path AGG_PATH]` launches the CLI agent with optional overrides for resume YAMLs and aggregation output.
- `uv run python scripts/run_all_tests.py` runs schema validation, pytest suites, and integration tests against the fixture dataset.
- `uv run pytest` executes the full test matrix; `uv run pytest --cov` captures coverage, while `python tests/run_all_tests.py` reproduces CI batches locally.

## Coding Style & Naming Conventions
- Follow Black-formatted Python (run `uv run black .`); the project assumes 4-space indentation, trailing commas, and 88-character lines.
- Prefer type hints and module-level constants in UPPER_SNAKE_CASE; keep functions/methods in snake_case and classes in PascalCase.
- Group agent prompt strings in dedicated helpers instead of inline literals to sustain reuse and testing.

## Testing Guidelines
- Use `pytest` with test files named `test_*.py`; fixture placement belongs in `tests/__init__.py` or dedicated `conftest.py` modules.
- Target resume/job parsing scenarios first; augment `tests/test_resume_operations.py` or add sibling modules under `tests/` for new behaviors.
- Ensure new features ship with coverage assertions and update `tests/run_all_tests.py` when adding orchestrated flows.

## Commit & Pull Request Guidelines
- Commits follow the existing imperative, present-tense style (e.g., "Add memory management..."); keep summaries under 72 characters and scope-focused.
- Reference linked issues in the body, list key changes, and note migrations or schema updates explicitly.
- Pull requests must describe validation steps (`uv run pytest`, manual scenario notes) and include screenshots or sample outputs when UI or resume formats change.

## Environment & Secrets
- Copy `sample.env` to `.env` and supply `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, plus optional `RESUME_DATA_DIR`, `RESUME_SUMMARY_PATH`, and `RESUME_JD_DIR` overrides before running agents.
- Never commit secrets; rely on repository-level environment variables for CI and document new configuration keys in project_docs.md.
