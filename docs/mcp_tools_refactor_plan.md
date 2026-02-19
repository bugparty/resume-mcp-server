# MCP Tools Parameters Unification and Renaming Refactoring Plan (2026-02)

## Background and Goals
Recently, `mcp_server.py` was refactored, but the MCP tools' external interfaces still have the following inconsistencies:
- Some tools use `filename` and require the `.yaml` suffix (e.g., `load_complete_resume`, `list_resume_sections`).
- Some tools use `version`, while others use `version_name`, leading to inconsistent parameter naming across tools.
- Section-related APIs support both `module_path` (e.g., `resume/summary`) and `(version_name, section_id)` styles, which is confusing and increases maintenance costs.
- `get_section_style` actually returns the "resume overall layout (section order + disabled)", so the name is not appropriate.

Goals of this refactoring:
1. **Unify version parameter to `version_name`** (without `.yaml` suffix).
2. **Unify section API to `(version_name, section_id)`** (no longer accept `module_path`).
3. **Rename `get_section_style` -> `get_resume_layout`** to express that it returns the overall layout.
4. **No compatibility layer**: Remove old parameter names/old tool names/old calling methods (breaking change).
5. Fix the mismatch between tool layer encapsulation and underlying function signatures to ensure runtime consistency.

## Design Decisions (Explicit Breaking)
- Only retain `version_name`, no longer accept `version`/`filename`.
- Only retain `(version_name, section_id)` style, no longer accept `module_path`.
- Tool renaming without aliases:
  - Delete `get_section_style`, add `get_resume_layout`.

## Target MCP Tool API (External)
The following are the tool signatures finally exposed through FastMCP (all in snake_case):

- `load_complete_resume(version_name: str) -> str`
  - Read `data/resumes/{version_name}.yaml` and render complete Markdown.

- `list_resume_sections(version_name: str) -> dict`
  - Return section list (recommended structured dict, not JSON string).

- `get_resume_section(version_name: str, section_id: str) -> str`
  - Return Markdown of the corresponding section.

- `update_resume_section(version_name: str, section_id: str, new_content: str) -> str`
  - Update corresponding section.

- `set_section_visibility(version_name: str, section_id: str, enabled: bool=True) -> dict`
  - Modify layout's section_disabled, and return updated layout.

- `set_section_order(version_name: str, order: list[str]) -> dict`
  - Modify layout's section_order, and return updated layout.

- `get_resume_layout(version_name: str) -> dict`
  - Return `{"section_order": [...], "section_disabled": {...}}`.

- `render_resume_pdf(version_name: str) -> dict`
- `submit_resume_pdf_job(version_name: str) -> dict`
- `render_resume_to_overleaf(version_name: str) -> dict`

> Note: section_id remains a string type to avoid enum limitations preventing access to custom sections (e.g., `additional`).

## Implementation Scope (Files and Modules)
### Core Files to Modify
- `src/myagent/mcp_server.py`
  - Adjust FastMCP tool definitions and parameter names.
  - Delete old `get_section_style`, add `get_resume_layout`.

- `src/myagent/tools.py`
  - Change Pydantic input models to `version_name` / `section_id`.
  - Unify StructuredTool encapsulation function signatures.
  - Fix signature mismatch between update_resume_section tool and `resume_loader.update_resume_section`.

- `src/myagent/resume_loader.py`
  - Provide read/write entry points based on `(version_name, section_id)`.
  - Refactor/rename interfaces mainly using `filename`, `module_path`.
  - Rename `get_section_style` to `get_resume_layout` (or corresponding implementation).

### Tests to Synchronize
- `tests/test_basic_functions.py`
- `tests/test_quick_version_workflow.py`
- `tests/test_resume_operations.py`
- And any tests calling `load_complete_resume("resume.yaml")` / `load_resume_section("resume/summary")`.

### Documents/Generated Artifacts to Update
- Rerun `./generate_all_docs.sh` to generate `mcp_tools_report.json`, `MCP_TOOLS.md`, `MCP_TOOLS.html`.

## Migration Guide (For MCP Clients/Callers)
- `filename` (e.g., `resume.yaml`) migrates to `version_name` (e.g., `resume`).
- `module_path` (e.g., `resume/summary`) migrates to:
  - `version_name="resume"`, `section_id="summary"`
- `get_section_style(version=...)` migrates to:
  - `get_resume_layout(version_name=...)`

## Acceptance Criteria
- `pytest` passes fully: `./.venv/bin/python -m pytest`
- `fastmcp inspect src/myagent/mcp_server.py` output tool parameters:
  - No `filename`, `module_path`, `version`.
  - `get_resume_layout` exists, `get_section_style` does not exist.
- `MCP_TOOLS.md/html` consistent with actual interface.

## Implementation Steps (Execution Order)
1. Modify `resume_loader.py`: Provide stable interface for version_name+section_id.
2. Modify `tools.py`: Unify encapsulation signatures and fix mismatches.
3. Modify `mcp_server.py`: Expose final MCP tool API.
4. Modify tests: Update calling methods.
5. Run `pytest`, fix residuals.
6. Run `./generate_all_docs.sh` to update documentation.
