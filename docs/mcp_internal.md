# MCP Internal Notes

This guide explains when the MCP stack reads schema files and what to update when the resume format changes.

## Schema locations
- `schemas/resume_schema.json`: Full resume YAML schema (metadata, sections, optional `style.section_order` and `style.section_disabled`).
- `schemas/resume_summary_schema.json`: Lightweight summary/index schema used for resume summaries.

## Where schemas are used
- CLI tools and MCP wrappers rely on valid resume YAMLs loaded via `resume_loader.py` and rendered by `resume_renderer.py`.
- Validation entrypoints: `scripts/validate_resume_yaml.py` and `scripts/run_all_tests.py` reference the resume schema to check YAMLs under `data/resumes` (or the configured data dir).
- Tests under `tests/fixtures/test_data` expect schema-compliant samples (e.g., `tests/fixtures/test_data/resumes/resume.yaml`).
- The MCP server (`src/myagent/mcp_server.py`) exposes tools that assume data matches the schema; malformed YAML will surface as tool errors during render/tailor flows.

## When to update schemas
- Whenever you add/change fields in resume YAML (metadata keys, section shapes, new section types, style options like ordering/disable flags), update `schemas/resume_schema.json` to match.
- If summary generation/output changes shape, update `schemas/resume_summary_schema.json`.
- Keep sample YAMLs in sync: `data/resumes/we_bible.yaml` and test fixtures under `tests/fixtures/test_data/resumes/` should reflect the current schema.

## Change workflow for resume schema
1) Edit `schemas/resume_schema.json` for new/changed fields (document required/optional fields; keep descriptions helpful).
2) Update sample resumes (`data/resumes/*.yaml`) and fixture resumes used by tests.
3) Adjust rendering/loader logic if the new fields affect ordering, visibility, or content (e.g., `_apply_section_style` in `resume_renderer.py`).
4) Add or update tests (e.g., `tests/test_resume_rendering.py`, `tests/test_resume_operations.py`) to cover the new behavior and defaults.
5) Update developer docs mentioning format (e.g., `docs/mcp_server.md`, `AGENTS.md`).

## Notes on section ordering/visibility
- Ordering and disable flags live under `style:` in the resume YAML.
- `section_order`: optional list of section ids; remaining sections append in original order.
- `section_disabled`: map of section ids to `true` to hide them; absent or `false` keeps them.
- Rendering applies these rules in `resume_renderer._apply_section_style`, used by both `render_resume` and `render_resume_from_dict`.

## Validation tips
- To validate locally: `uv run python scripts/validate_resume_yaml.py` or run the full test suite `uv run pytest` / `uv run python scripts/run_all_tests.py`.
- For quick checks on a single file, point `TEST_RESUME_DATA_DIR` to a temp directory containing that YAML and run the validation script.
