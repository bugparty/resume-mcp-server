# Architecture

```
src/resume_platform/
├── interfaces/mcp/        # MCP adapter — thin
│   ├── server.py          # builds the FastMCP app, HTTP/stdio entry points
│   ├── tools.py           # one function per tool + the TOOLS registry
│   ├── telemetry.py       # call logging, failure log, /error-logs
│   └── prompts.py         # agent prompt, YAML format documentation
├── resume/                # the domain
│   ├── repository.py      # <version>.yaml persistence, name validation
│   ├── versions.py        # create / copy / delete versions
│   ├── layout.py          # section order & visibility (style block)
│   ├── views.py           # YAML -> Markdown text view
│   └── editing.py         # Markdown edits -> parsed, validated YAML
├── resume_input_parser.py # Markdown section parsers used by editing
├── resume_renderer.py     # YAML -> LaTeX (Jinja templates) + remote compile
├── publishing.py          # PDF / Overleaf export to output storage + S3
├── vector_search.py       # Chroma index over experience/project entries
├── paths.py               # repo locations (templates, schemas)
└── infrastructure/        # settings, filesystems, bootstrap, S3, embeddings
```

Dependencies point inward: `interfaces` → `publishing` / `vector_search` →
`resume` → `infrastructure`. Nothing in `resume/` knows about MCP.

## Runtime lifecycle

Importing modules has no side effects. Each entry point calls
`infrastructure.bootstrap.bootstrap()` once, which resolves settings and opens
the resume / JD / output filesystems (local directories or S3 via
PyFilesystem2). The MCP server does this in `server.start_runtime()`; tests
do it per test in `tests/conftest.py`. See
[ADR-0001](adr/0001-composition-root-and-runtime-lifecycle.md).

## Data model

One YAML document per version (`resumes/<version_name>.yaml`) validated by
`schemas/resume_schema.json`: `metadata` (the header), a list of `sections`
(`summary`, `skills`, `experience`, `projects`, `education`, `raw`) and an
optional `style` block (`section_order`, `section_disabled`). New versions
start from `templates/resume_template.yaml`.

Editing goes through a Markdown view: `views` renders a section (or the whole
resume) to Markdown, the client edits text, `editing` parses it back with the
section's parser, validates the result (non-empty, single section, matching
heading…) and only then saves. A failed edit never writes.

## MCP tool conventions

- Address resumes by `version_name`, sections by `section_id`; text tools take
  an optional `section_id` (omitted = whole resume).
- Raise on failure with an actionable message; FastMCP returns it as a tool
  error. Do not return `"[Error] ..."` strings or `{"error": ...}` payloads.
- Reads return dicts or Markdown; writes return a confirmation (or the
  updated layout).
- Keep tool functions thin; put logic in the domain modules.

### Adding a tool

1. Implement the behaviour in the domain (`resume/`, `publishing.py`, …) with
   unit tests.
2. Add a function to `interfaces/mcp/tools.py` using the `VersionName` /
   `SectionId` annotated types, with a docstring written for the LLM.
3. Register it in `TOOLS` (`_read`, `_write`, or a `ToolSpec` for special
   annotations). `_write` tools automatically mark the vector index stale.
4. Add it to `EXPECTED_TOOLS` and a round-trip test in
   `tests/test_mcp_server.py`.
5. Add it to a section in `scripts/generate_mcp_docs.py` and regenerate
   `docs/mcp_tools.md` (a test fails if you forget).
