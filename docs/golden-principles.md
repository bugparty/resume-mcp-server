# Golden principles

The rules that keep this codebase from drifting. Each one says what enforces
it:

- **CI** means a test or lint step fails the build. Most rules live in
  `tests/test_structure.py`.
- **Sweep** means a periodic clean-up agent checks it, because a script can't
  judge it reliably.

When the same kind of problem is found twice, turn it into a CI check. Rules
only get stricter.

Formatting and lint style is Ruff's job (`pyproject.toml`); it isn't repeated
here.

## 1. Dependencies point inward

`interfaces/` → `publishing` / `vector_search` → `resume_renderer` →
`resume/` → `infrastructure/` → `paths`. Nothing in `resume/` knows about MCP;
nothing in `infrastructure/` knows what a resume is.

*CI:* `test_dependencies_point_inward`

## 2. Resume persistence goes through the repository

Only `resume/repository.py` knows the `<version_name>.yaml` layout or calls
`get_resume_fs()` for resumes; everyone else uses `load_resume` /
`save_resume`. Version names are validated there. The few raw-storage users
(the `data://` resource, `diagnose_filesystems`) are allow-listed with a
reason.

*CI:* `test_resume_storage_is_only_touched_by_the_repository`

## 3. Failures raise

No `"[Error] ..."` strings, no `return {"error": ...}`. Raise an exception
with a message that says what to do next ("Did you mean 'summary'?"); MCP
clients receive it as a tool error.

*CI:* `test_failures_raise_instead_of_returning_errors`

## 4. MCP tools are thin and consistent

Tool functions forward to the domain layer. Resumes are addressed by
`version_name`, sections by an optional `section_id`; every parameter has a
`Field(description=...)`. The tool surface is pinned by a contract test and
the reference docs are generated from it.

*CI:* `test_mcp_tools_are_thin`, `tests/test_mcp_server.py`,
`test_mcp_docs.py`

## 5. Importing has no side effects

Importing any module must not read settings, create directories, open files
or connect to storage. Runtime state is assembled only by `bootstrap()`
(see [ADR-0001](adr/0001-composition-root-and-runtime-lifecycle.md)).

*CI:* `test_importing_every_module_has_no_side_effects`

## 6. Repository paths come from `paths.py`

No `Path(__file__).parents[N]`; it breaks silently when files move.

*CI:* `test_no_parent_path_arithmetic`

## 7. Tests fake only the network and never touch the repo

Fake the LaTeX compile service, S3 and embedding providers; use real
rendering and storage everywhere else. Every test gets a private copy of the
fixture data (`tests/conftest.py`).

*CI:* the "Tests must not modify the repository" step.
*Sweep:* new mocks of internal modules.

## 8. One copy of each piece of logic

Before writing a helper, look for an existing one; when you find a second
copy, merge them. (Section layout and LaTeX asset staging were each
duplicated 2–3× before the 2026-11 refactor.)

*Sweep:* look for near-duplicate functions and repeated blocks.

## 9. Docs describe the present

File paths mentioned in docs must exist. Tool docs are generated. Design
docs that are implemented, superseded or abandoned say so in a status line at
the top and are then exempt from the path check.

*CI:* `test_docs_reference_existing_files`, `test_historical_docs_are_marked`,
`test_mcp_docs.py`.
*Sweep:* prose that no longer matches behaviour.

## 10. Delete what nobody uses

No code, scripts, config or binaries kept "just in case"; git history
remembers them.

*CI:* Ruff (unused imports and variables), `test_no_unreferenced_files`
(scripts, schemas, templates, fixtures and top-level shell scripts must be
mentioned somewhere).
*Sweep:* `uvx vulture src scripts --min-confidence 60` (expect false
positives on decorator-registered functions), plus unreferenced scripts and
config files.

---

## Running a sweep

A sweep is an agent session that:

1. reads this file and `docs/architecture.md`;
2. looks only for the *Sweep* items above, since CI already covers the rest;
3. opens one small PR per finding, each passing `./run_tests.sh`;
4. when a kind of finding repeats, proposes a CI check for it instead.
