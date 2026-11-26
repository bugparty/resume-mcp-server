"""Contract tests for the MCP server, exercised through a real MCP client.

These pin down the public tool surface (names, parameters, annotations) and
check every tool end-to-end over the protocol, the same way Claude / ChatGPT
call it. If you add, rename or change a tool, update EXPECTED_TOOLS and the
generated docs (scripts/generate_mcp_docs.py).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from resume_platform import vector_search
from resume_platform.interfaces.mcp import server, telemetry

# name -> (required params, optional params, readOnlyHint)
EXPECTED_TOOLS: dict[str, tuple[set[str], set[str], bool]] = {
    "call_me_at_the_first_time_when_you_are_chatgpt": (set(), set(), True),
    "list_resume_versions": (set(), set(), True),
    "create_resume_version": ({"version_name"}, set(), False),
    "copy_resume_version": ({"source_version", "target_version"}, set(), False),
    "delete_resume_version": ({"version_name"}, set(), False),
    "load_complete_resume": ({"version_name"}, set(), True),
    "list_resume_sections": ({"version_name"}, set(), True),
    "read_resume_text": ({"version_name"}, {"section_id"}, True),
    "replace_resume_text": (
        {"version_name", "old_text", "new_text"},
        {"section_id"},
        False,
    ),
    "insert_resume_text": (
        {"version_name", "new_text", "position"},
        {"anchor_text", "section_id"},
        False,
    ),
    "delete_resume_text": ({"version_name", "old_text"}, {"section_id"}, False),
    "update_resume_section": (
        {"version_name", "section_id", "new_content"},
        set(),
        False,
    ),
    "get_resume_layout": ({"version_name"}, set(), True),
    "set_section_visibility": ({"version_name", "section_id"}, {"enabled"}, False),
    "set_section_order": ({"version_name", "order"}, set(), False),
    "build_vector_index": (set(), {"force_rebuild"}, False),
    "search_resume_entries": (
        {"query"},
        {"entry_type", "chunk_level", "top_k"},
        True,
    ),
    "get_vector_index_status": (set(), set(), True),
    "render_resume_pdf": ({"version_name"}, set(), False),
    "render_resume_to_overleaf": ({"version_name"}, set(), False),
    "get_resume_yaml_format": (set(), set(), True),
    "diagnose_filesystems": (set(), set(), True),
}


def run(coro):
    return asyncio.run(coro)


async def _call(name: str, args: dict[str, Any] | None = None):
    async with Client(server.mcp) as client:
        return await client.call_tool(name, args or {}, raise_on_error=False)


def call(name: str, **args: Any) -> Any:
    """Call a tool over MCP; return its data, failing the test on tool errors."""
    result = run(_call(name, args))
    assert not result.is_error, result.content[0].text
    return result.data


def call_error(name: str, **args: Any) -> str:
    """Call a tool expected to fail; return the error text."""
    result = run(_call(name, args))
    assert result.is_error, f"{name} unexpectedly succeeded: {result.data!r}"
    return result.content[0].text


@pytest.fixture(autouse=True)
def error_log(tmp_path, monkeypatch):
    log = telemetry.ErrorEventLog(tmp_path / "errors.jsonl")
    monkeypatch.setattr(telemetry, "error_log", log)
    return log


# --- surface ------------------------------------------------------------------


def test_tool_surface_matches_contract() -> None:
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in run(list_tools())}
    assert set(tools) == set(EXPECTED_TOOLS)

    for name, (required, optional, read_only) in EXPECTED_TOOLS.items():
        schema = tools[name].inputSchema
        assert set(schema.get("required", [])) == required, name
        assert set(schema["properties"]) == required | optional, name
        assert tools[name].annotations.readOnlyHint is read_only, name
        assert tools[name].description, f"{name} has no description"


def test_parameters_are_documented_and_enums_exposed() -> None:
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in run(list_tools())}
    insert = tools["insert_resume_text"].inputSchema["properties"]
    assert insert["position"]["enum"] == ["start", "end", "before", "after"]
    assert "description" in insert["version_name"]
    assert "description" in insert["section_id"]


def test_destructive_tools_are_flagged() -> None:
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in run(list_tools())}
    assert tools["delete_resume_version"].annotations.destructiveHint is True
    assert tools["render_resume_pdf"].annotations.openWorldHint is True


# --- versions -----------------------------------------------------------------


def test_version_lifecycle() -> None:
    assert "resume" in call("list_resume_versions")["versions"]

    call("copy_resume_version", source_version="resume", target_version="google")
    call("create_resume_version", version_name="blank")
    versions = call("list_resume_versions")
    assert {"google", "blank"} <= set(versions["versions"])
    assert versions["total"] == len(versions["versions"])

    call("delete_resume_version", version_name="google")
    assert "google" not in call("list_resume_versions")["versions"]


def test_version_errors_are_tool_errors() -> None:
    assert "base resume version" in call_error(
        "delete_resume_version", version_name="resume"
    )
    assert "already exists" in call_error(
        "create_resume_version", version_name="resume"
    )
    assert ".yaml" in call_error("load_complete_resume", version_name="resume.yaml")
    assert "not found" in call_error("load_complete_resume", version_name="missing")


# --- reading & editing --------------------------------------------------------


def test_reading_tools() -> None:
    markdown = call("load_complete_resume", version_name="resume")
    assert markdown.startswith("# ")
    assert "## Summary" in markdown

    sections = call("list_resume_sections", version_name="resume")
    assert sections["sections"][0]["id"] == "header"
    assert sections["total"] == len(sections["sections"])

    whole = call("read_resume_text", version_name="resume")
    assert "## Header" in whole and "## Summary" in whole
    one = call("read_resume_text", version_name="resume", section_id="summary")
    assert "## Summary" in one and "## Header" not in one


def test_section_typo_suggests_fix() -> None:
    error = call_error("read_resume_text", version_name="resume", section_id="sumary")
    assert "Did you mean 'summary'?" in error


def test_text_editing_round_trip() -> None:
    call("copy_resume_version", source_version="resume", target_version="edit")
    summary = call("read_resume_text", version_name="edit", section_id="summary")
    first_bullet = next(line for line in summary.splitlines() if line.startswith("- "))

    call(
        "replace_resume_text",
        version_name="edit",
        section_id="summary",
        old_text=first_bullet,
        new_text="- Replaced over MCP",
    )
    call(
        "insert_resume_text",
        version_name="edit",
        section_id="summary",
        new_text="\n- Inserted at end",
        position="end",
    )
    call(
        "insert_resume_text",
        version_name="edit",
        section_id="summary",
        new_text="- Before anchor\n",
        position="before",
        anchor_text="- Replaced over MCP",
    )
    call(
        "delete_resume_text",
        version_name="edit",
        section_id="summary",
        old_text="\n- Inserted at end",
    )

    summary = call("read_resume_text", version_name="edit", section_id="summary")
    assert "- Before anchor\n- Replaced over MCP" in summary
    assert "Inserted at end" not in summary
    assert first_bullet not in summary


def test_whole_resume_text_edit() -> None:
    call(
        "replace_resume_text",
        version_name="resume",
        old_text="## Header",
        new_text="## Header\nwebsite: example.dev",
    )
    header = call("read_resume_text", version_name="resume", section_id="header")
    assert "website: example.dev" in header


def test_editing_errors() -> None:
    assert "was not found" in call_error(
        "replace_resume_text", version_name="resume", old_text="zzz", new_text="y"
    )
    assert "requires `anchor_text`" in call_error(
        "insert_resume_text", version_name="resume", new_text="x", position="after"
    )
    # Invalid enum values are rejected by schema validation before the tool runs.
    call_error(
        "insert_resume_text", version_name="resume", new_text="x", position="middle"
    )


def test_update_resume_section() -> None:
    message = call(
        "update_resume_section",
        version_name="resume",
        section_id="summary",
        new_content="## Summary\n- Rewritten via MCP",
    )
    assert "Updated resume/summary" in message
    assert "Rewritten via MCP" in call(
        "read_resume_text", version_name="resume", section_id="summary"
    )

    error = call_error(
        "update_resume_section",
        version_name="resume",
        section_id="summary",
        new_content="## Summary\n- a\n\n## Skills\n- Python: x",
    )
    assert "only one section at a time" in error


# --- layout -------------------------------------------------------------------


def test_layout_tools() -> None:
    assert call("get_resume_layout", version_name="resume") == {
        "version_name": "resume",
        "section_order": [],
        "section_disabled": {},
    }
    hidden = call(
        "set_section_visibility",
        version_name="resume",
        section_id="summary",
        enabled=False,
    )
    assert hidden["section_disabled"] == {"summary": True}
    assert "## Summary" not in call("load_complete_resume", version_name="resume")

    ordered = call("set_section_order", version_name="resume", order=["skills", "nope"])
    assert ordered["section_order"] == ["skills"]
    assert ordered["skipped_ids"] == ["nope"]
    assert call("get_resume_layout", version_name="resume")["section_order"] == [
        "skills"
    ]


# --- index invalidation -------------------------------------------------------


def test_write_tools_mark_vector_index_stale(monkeypatch) -> None:
    reasons: list[str] = []
    monkeypatch.setattr(server, "mark_index_stale", reasons.append)

    call("list_resume_versions")
    call("read_resume_text", version_name="resume")
    assert reasons == []

    call("copy_resume_version", source_version="resume", target_version="x")
    call("set_section_order", version_name="x", order=["skills"])
    assert reasons == ["copy_resume_version", "set_section_order"]

    call_error("delete_resume_version", version_name="resume")
    assert reasons == ["copy_resume_version", "set_section_order"]


def test_search_tools_delegate_to_vector_search(monkeypatch) -> None:
    seen = {}

    def fake_search(**kwargs):
        seen.update(kwargs)
        return {"results": [], "result_count": 0}

    monkeypatch.setattr(vector_search, "search_entries", fake_search)
    monkeypatch.setattr(vector_search, "get_index_status", lambda: {"stale": True})
    monkeypatch.setattr(
        vector_search, "build_index", lambda force_rebuild: {"built": force_rebuild}
    )

    assert call("search_resume_entries", query="kafka", entry_type="projects") == {
        "results": [],
        "result_count": 0,
    }
    assert seen == {
        "query": "kafka",
        "entry_type": "projects",
        "chunk_level": "entry",
        "top_k": 5,
    }
    assert call("get_vector_index_status") == {"stale": True}
    assert call("build_vector_index", force_rebuild=True) == {"built": True}


# --- rendering, help, diagnostics ---------------------------------------------


def test_render_tools_delegate_to_publishing(monkeypatch) -> None:
    from resume_platform import publishing

    monkeypatch.setattr(
        publishing, "publish_pdf", lambda v: {"public_url": f"u/{v}.pdf"}
    )
    monkeypatch.setattr(
        publishing, "publish_overleaf", lambda v: {"overleaf_url": f"o/{v}"}
    )
    assert call("render_resume_pdf", version_name="resume") == {
        "public_url": "u/resume.pdf"
    }
    assert call("render_resume_to_overleaf", version_name="resume") == {
        "overleaf_url": "o/resume"
    }


def test_help_and_diagnostics() -> None:
    doc = call("get_resume_yaml_format")
    assert "Schema file not found" not in doc
    assert '"$schema"' in doc or '"properties"' in doc

    assert "version_name" in call("call_me_at_the_first_time_when_you_are_chatgpt")

    report = call("diagnose_filesystems")
    assert report["initialized"] is True
    assert "resume" in report["versions"]
    assert report["resume_fs"]["count"] >= 1


def test_prompt_and_resources() -> None:
    async def go():
        async with Client(server.mcp) as client:
            prompt = await client.get_prompt("resume_agent_prompt")
            resume = await client.read_resource("data://resumes/resume.yaml")
            jd = await client.read_resource("data://jd/tesla.txt")
            return prompt, resume, jd

    prompt, resume, jd = run(go())
    assert "version_name" in prompt.messages[0].content.text
    assert resume[0].text.lstrip().startswith(("source:", "metadata:"))
    assert jd[0].text


def test_resource_rejects_escape_and_unknown_roots() -> None:
    async def read(uri):
        async with Client(server.mcp) as client:
            return await client.read_resource(uri)

    for uri in ("data://resumes/../secret.yaml", "data://etc/passwd"):
        with pytest.raises(Exception):
            run(read(uri))


# --- telemetry ----------------------------------------------------------------


def test_failed_tool_calls_are_recorded(error_log) -> None:
    call_error("load_complete_resume", version_name="missing")
    events, parse_errors = error_log.read()
    assert parse_errors == 0
    [event] = events
    assert event["tool_name"] == "load_complete_resume"
    assert event["failure_kind"] == "exception"
    assert event["error_type"] == "ResumeNotFoundError"
    assert event["kwargs"] == {"version_name": "missing"}
    assert "Traceback" in event["traceback"]


def test_in_band_error_payloads_are_recorded(error_log) -> None:
    @telemetry.log_tool_call
    def legacy_tool() -> str:
        return json.dumps({"error": "bad request", "code": 400})

    legacy_tool()
    [event] = error_log.read()[0]
    assert event["failure_kind"] == "error_response"
    assert event["error_message"] == "bad request"
    assert event["result_payload"]["code"] == 400


# --- HTTP app -----------------------------------------------------------------


@pytest.fixture
def http_client():
    return TestClient(server.create_http_app())


def test_http_app_routes_and_health(http_client) -> None:
    paths = {getattr(route, "path", None) for route in http_client.app.routes}
    assert {"/mcp", "/sse", "/messages", "/health", "/error-logs"} <= paths
    assert http_client.get("/health").text == "OK"


def test_http_app_cors(http_client) -> None:
    response = http_client.options(
        "/sse",
        headers={
            "Origin": "chrome-extension://example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_error_logs_endpoint_validation(http_client) -> None:
    body = http_client.get("/error-logs").json()
    assert body["total"] == 0 and body["items"] == []
    for query in ("limit=0", "limit=x", "offset=-1", "failure_kind=bad"):
        assert http_client.get(f"/error-logs?{query}").status_code == 400


def test_error_logs_endpoint_filters_and_pages(http_client, error_log) -> None:
    for event_id, ts, tool, kind in [
        ("1", "2026-03-28T10:00:00+00:00", "tool_a", "exception"),
        ("2", "2026-03-28T11:00:00+00:00", "tool_b", "error_response"),
        ("3", "2026-03-28T12:00:00+00:00", "tool_a", "exception"),
    ]:
        error_log.append(
            {
                "event_id": event_id,
                "timestamp": ts,
                "tool_name": tool,
                "failure_kind": kind,
            }
        )
    with error_log.path.open("a", encoding="utf-8") as handle:
        handle.write("{bad json\n")

    body = http_client.get("/error-logs").json()
    assert body["total"] == 3
    assert body["items"][0]["event_id"] == "3"
    assert body["parse_errors"] == 1

    page = http_client.get(
        "/error-logs?tool_name=tool_a&failure_kind=exception&limit=1&offset=1"
    ).json()
    assert page["total"] == 2
    assert [item["event_id"] for item in page["items"]] == ["1"]
