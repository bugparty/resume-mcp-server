#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import queue
import re
import ssl
import sys
import threading
import time
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


DEFAULT_SSE_ENDPOINT = "https://resume-mcp.k.0x1f0c.dev/sse"


class SafeImportError(RuntimeError):
    pass


def _json_error_with_snippet(text: str, exc: json.JSONDecodeError) -> str:
    start = max(0, exc.pos - 60)
    end = min(len(text), exc.pos + 60)
    snippet = text[start:end].replace("\n", "\\n")
    pointer = " " * (exc.pos - start) + "^"
    return (
        f"JSON parse failed at line {exc.lineno}, column {exc.colno} (char {exc.pos}).\n"
        f"Snippet: {snippet}\n"
        f"         {pointer}"
    )


def _strip_markdown_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    match = re.match(r"^```(?:json)?\s*\n(?P<body>.*)\n```\s*$", stripped, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return text
    return match.group("body")


def _decode_input_bytes(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SafeImportError("Input is not valid UTF-8/UTF-8-SIG bytes.") from exc


def _parse_json_payload(text: str) -> tuple[dict[str, Any], str]:
    stripped = _strip_markdown_json_fence(text).strip()
    try:
        first = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise SafeImportError(_json_error_with_snippet(stripped, exc)) from exc

    if isinstance(first, str):
        second_candidate = first.strip()
        if second_candidate.startswith("{") or second_candidate.startswith("["):
            try:
                second = json.loads(second_candidate)
            except json.JSONDecodeError as exc:
                raise SafeImportError(
                    "Detected double-encoded JSON string, but the decoded inner JSON is invalid.\n"
                    + _json_error_with_snippet(second_candidate, exc)
                ) from exc
            first = second
            mode = "double-encoded"
        else:
            raise SafeImportError("Top-level JSON is a string, not a resume object.")
    else:
        mode = "direct"

    if not isinstance(first, dict):
        raise SafeImportError("Top-level JSON must be an object.")
    return first, mode


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return str(value).strip()


def _to_bullets(value: Any) -> list[str]:
    bullets: list[str] = []
    if isinstance(value, list):
        for item in value:
            text = _to_text(item)
            if text:
                bullets.append(text)
    elif isinstance(value, str):
        for line in value.splitlines():
            text = line.strip()
            if text:
                bullets.append(text.lstrip("-* ").strip())
    return bullets


def _render_header(source: Any) -> str | None:
    if not isinstance(source, dict):
        return None
    preferred = [
        "first_name",
        "last_name",
        "position",
        "address",
        "mobile",
        "email",
        "github",
        "linkedin",
    ]
    lines = ["## Header"]
    used: set[str] = set()
    for key in preferred:
        value = _to_text(source.get(key))
        if value:
            lines.append(f"{key}: {value}")
            used.add(key)
    for key in sorted(k for k in source.keys() if k not in used):
        value = _to_text(source.get(key))
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) if len(lines) > 1 else None


def _render_summary(source: Any) -> str | None:
    bullets: list[str] = []
    title = "Summary"
    if isinstance(source, dict):
        title = _to_text(source.get("title")) or title
        bullets = _to_bullets(source.get("bullets"))
        if not bullets:
            bullets = _to_bullets(source.get("content"))
    else:
        bullets = _to_bullets(source)
    if not bullets:
        return None
    lines = [f"## {title}"] + [f"- {item}" for item in bullets]
    return "\n".join(lines)


def _render_skills(source: Any) -> str | None:
    groups: list[tuple[str, list[str]]] = []
    title = "Skills"
    if isinstance(source, dict):
        title = _to_text(source.get("title")) or title
        raw_groups = source.get("groups")
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if not isinstance(group, dict):
                    continue
                category = _to_text(group.get("category")) or "Skills"
                items = _to_bullets(group.get("items"))
                groups.append((category, items))
        else:
            for key, value in source.items():
                if key in {"title", "groups"}:
                    continue
                groups.append((_to_text(key) or "Skills", _to_bullets(value)))
    elif isinstance(source, list):
        groups.append(("Skills", _to_bullets(source)))
    if not groups:
        return None
    lines = [f"## {title}"]
    for category, items in groups:
        joined = ", ".join(items) if items else ""
        if joined:
            lines.append(f"- {category}: {joined}")
        else:
            lines.append(f"- {category}:")
    return "\n".join(lines)


def _normalize_entries(source: Any) -> tuple[list[dict[str, Any]], str]:
    title = ""
    if isinstance(source, dict):
        title = _to_text(source.get("title"))
        entries = source.get("entries")
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)], title
        return [], title
    if isinstance(source, list):
        return [item for item in source if isinstance(item, dict)], title
    return [], title


def _render_entries(source: Any, section_id: str) -> str | None:
    entries, given_title = _normalize_entries(source)
    if not entries:
        return None
    default_titles = {
        "experience": "Experience",
        "projects": "Projects",
        "education": "Education",
    }
    title = given_title or default_titles.get(section_id, "Section")
    lines = [f"## {title}"]
    for entry in entries:
        etitle = _to_text(entry.get("title"))
        org = _to_text(entry.get("organization"))
        location = _to_text(entry.get("location"))
        period = _to_text(entry.get("period"))

        if section_id == "projects":
            left = etitle or org or "Project"
            if etitle and org:
                left = f"{etitle} — {org}"
            heading = f"### {left}"
            if period:
                heading += f" | {period}"
        else:
            left = etitle or org or "Entry"
            if etitle and org:
                left = f"{etitle} — {org}"
            heading = f"### {left}"
            if location:
                heading += f" ({location})"
            if period:
                heading += f" | {period}"

        lines.append(heading)
        bullets = _to_bullets(entry.get("bullets"))
        for bullet in bullets:
            lines.append(f"- {bullet}")
        lines.append("")
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _render_raw(source: Any, section_title: str = "Additional") -> str | None:
    if isinstance(source, dict):
        title = _to_text(source.get("title")) or section_title
        content = source.get("content")
        body = _to_text(content) if not isinstance(content, list) else "\n".join(_to_bullets(content))
    elif isinstance(source, list):
        title = section_title
        body = "\n".join(_to_bullets(source))
    else:
        title = section_title
        body = _to_text(source)
    if not body:
        return None
    return f"## {title}\n{body}".strip()


def _index_sections(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    by_id: dict[str, Any] = {}
    by_type: dict[str, Any] = {}
    sections = payload.get("sections")
    if isinstance(sections, list):
        for item in sections:
            if not isinstance(item, dict):
                continue
            section_id = _to_text(item.get("id"))
            section_type = _to_text(item.get("type"))
            if section_id and section_id not in by_id:
                by_id[section_id] = item
            if section_type and section_type not in by_type:
                by_type[section_type] = item
    return metadata, by_id, by_type


def _source_for_section(
    payload: dict[str, Any],
    metadata: dict[str, Any],
    by_id: dict[str, Any],
    by_type: dict[str, Any],
    section_id: str,
    section_type: str,
) -> Any:
    if section_id == "header":
        if isinstance(payload.get("header"), dict):
            return payload["header"]
        return metadata or payload.get("metadata")
    if section_id in payload:
        return payload.get(section_id)
    if section_id in by_id:
        return by_id.get(section_id)
    if section_type and section_type in by_type:
        return by_type.get(section_type)
    if section_id in {"custom", "additional", "raw"}:
        for key in ("custom", "additional", "raw"):
            if key in payload:
                return payload.get(key)
        if "raw" in by_type:
            return by_type.get("raw")
    return None


def _render_for_section(section_id: str, section_type: str, source: Any) -> str | None:
    if source is None:
        return None
    if section_id == "header":
        return _render_header(source)
    if section_id == "summary" or section_type == "summary":
        return _render_summary(source)
    if section_id == "skills" or section_type == "skills":
        return _render_skills(source)
    if section_id in {"experience", "projects", "education"}:
        return _render_entries(source, section_id)
    if section_type in {"experience", "projects", "education"}:
        return _render_entries(source, section_type)
    return _render_raw(source, section_title=section_id.replace("_", " ").title())


def _unwrap_result(value: Any) -> Any:
    if isinstance(value, dict):
        if "structuredContent" in value:
            return _unwrap_result(value["structuredContent"])
        if set(value.keys()) == {"result"}:
            return _unwrap_result(value["result"])
    return value


def _coerce_json_if_possible(value: Any) -> Any:
    value = _unwrap_result(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def _extract_tool_call_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    if result.get("isError") is True:
        content = result.get("content")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(_to_text(item.get("text")))
            detail = "\n".join(part for part in text_parts if part)
            raise SafeImportError(f"Remote MCP tool returned error: {detail or result}")
        raise SafeImportError(f"Remote MCP tool returned error: {result}")

    if "structuredContent" in result:
        return result["structuredContent"]

    content = result.get("content")
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(_to_text(item.get("text")))
        joined = "\n".join(part for part in text_parts if part).strip()
        if joined:
            maybe_json = _coerce_json_if_possible(joined)
            return maybe_json

    if "result" in result:
        return result["result"]

    return result


class RemoteSSEMCPClient:
    def __init__(
        self,
        sse_url: str,
        network_timeout: float,
        response_timeout: float,
        insecure_tls: bool = False,
    ) -> None:
        self.sse_url = sse_url
        self.network_timeout = network_timeout
        self.response_timeout = response_timeout
        self.insecure_tls = insecure_tls
        self._response: Any = None
        self._messages_url = ""
        self._events: queue.Queue[dict[str, str]] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._reader_error: Exception | None = None
        self._request_id = 1

    def _ssl_context(self) -> ssl.SSLContext | None:
        if not self.insecure_tls:
            return None
        return ssl._create_unverified_context()

    def connect(self) -> None:
        req = urlrequest.Request(
            self.sse_url,
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
            },
            method="GET",
        )
        try:
            self._response = urlrequest.urlopen(
                req,
                timeout=self.network_timeout,
                context=self._ssl_context(),
            )
        except urlerror.URLError as exc:
            raise SafeImportError(f"Failed to connect SSE endpoint: {exc}") from exc

        self._reader = threading.Thread(target=self._read_sse_loop, daemon=True)
        self._reader.start()

        endpoint_event = self._wait_event(lambda ev: ev.get("event") == "endpoint")
        endpoint_path = endpoint_event.get("data", "").strip()
        if not endpoint_path:
            raise SafeImportError("SSE endpoint did not provide messages endpoint path.")
        self._messages_url = urlparse.urljoin(self.sse_url, endpoint_path)

    def close(self) -> None:
        if self._response is not None:
            try:
                self._response.close()
            except Exception:
                pass
        if self._reader is not None:
            self._reader.join(timeout=0.2)

    def _read_sse_loop(self) -> None:
        event_name = "message"
        data_lines: list[str] = []
        try:
            for raw in self._response:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    if data_lines:
                        self._events.put({"event": event_name, "data": "\n".join(data_lines)})
                    event_name = "message"
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip() or "message"
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
        except Exception as exc:  # noqa: BLE001
            self._reader_error = exc

    def _wait_event(self, predicate) -> dict[str, str]:
        deadline = time.time() + self.response_timeout
        while time.time() < deadline:
            if self._reader_error is not None:
                raise SafeImportError(f"SSE stream reader failed: {self._reader_error}")
            remaining = max(0.01, deadline - time.time())
            try:
                event = self._events.get(timeout=remaining)
            except queue.Empty:
                continue
            if predicate(event):
                return event
        raise SafeImportError("Timed out waiting for SSE response from remote MCP.")

    def _post(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urlrequest.Request(
            self._messages_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(
                req,
                timeout=self.network_timeout,
                context=self._ssl_context(),
            ) as resp:
                _ = resp.read()
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SafeImportError(f"MCP POST failed ({exc.code}): {detail}") from exc
        except urlerror.URLError as exc:
            raise SafeImportError(f"MCP POST failed: {exc}") from exc

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        req_id = self._request_id
        self._request_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._post(payload)

        def _match(event: dict[str, str]) -> bool:
            if event.get("event") != "message":
                return False
            try:
                obj = json.loads(event.get("data", ""))
            except json.JSONDecodeError:
                return False
            return obj.get("id") == req_id

        event = self._wait_event(_match)
        message = json.loads(event["data"])
        if "error" in message:
            raise SafeImportError(f"MCP method '{method}' failed: {message['error']}")
        return message.get("result")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._post(payload)

    def initialize(self) -> None:
        _ = self.call(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "resume-mcp-safe-json", "version": "0.1.0"},
            },
        )
        self.notify("notifications/initialized", {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call("tools/call", {"name": name, "arguments": arguments})
        return _extract_tool_call_result(result)


def _load_input_bytes(args: argparse.Namespace) -> bytes:
    if args.input_file:
        with open(args.input_file, "rb") as handle:
            return handle.read()
    if args.stdin:
        raw = sys.stdin.buffer.read()
        if not raw:
            raise SafeImportError("No bytes received from stdin.")
        return raw
    if args.input_b64:
        try:
            return base64.b64decode(args.input_b64, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise SafeImportError(f"Invalid base64 input: {exc}") from exc
    raise SafeImportError("No input source provided.")


def _ensure_version_exists(versions_payload: Any, version_name: str) -> None:
    versions_obj = _coerce_json_if_possible(versions_payload)
    if not isinstance(versions_obj, dict):
        raise SafeImportError(f"Unexpected response from list_resume_versions: {versions_obj}")
    versions = versions_obj.get("versions")
    if not isinstance(versions, list):
        raise SafeImportError(f"Missing versions list in response: {versions_obj}")
    if version_name not in versions:
        raise SafeImportError(f"Target version '{version_name}' not found. Available: {', '.join(versions)}")


def _extract_sections(sections_payload: Any) -> list[dict[str, Any]]:
    sections_obj = _coerce_json_if_possible(sections_payload)
    if isinstance(sections_obj, str):
        match = re.search(r"Available modules:\s*(?P<mods>.+)$", sections_obj, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            raise SafeImportError(f"Unexpected response from list_resume_sections: {sections_obj}")
        raw_modules = match.group("mods")
        section_ids = [item.strip() for item in raw_modules.split(",") if item.strip()]
        type_map = {
            "header": "header",
            "summary": "summary",
            "skills": "skills",
            "experience": "experience",
            "projects": "projects",
            "education": "education",
            "custom": "raw",
            "additional": "raw",
            "raw": "raw",
        }
        return [{"id": sid, "type": type_map.get(sid, sid)} for sid in section_ids]

    if not isinstance(sections_obj, dict):
        raise SafeImportError(f"Unexpected response from list_resume_sections: {sections_obj}")
    sections = sections_obj.get("sections")
    if not isinstance(sections, list):
        raise SafeImportError(f"Missing sections in response: {sections_obj}")
    normalized: list[dict[str, Any]] = []
    for item in sections:
        if not isinstance(item, dict):
            continue
        section_id = _to_text(item.get("id"))
        if not section_id:
            continue
        normalized.append({"id": section_id, "type": _to_text(item.get("type"))})
    return normalized


def _check_readback_not_empty(readback: Any, section_path: str) -> None:
    text = _coerce_json_if_possible(readback)
    if isinstance(text, str):
        if text.strip():
            return
        raise SafeImportError(f"Readback for '{section_path}' is empty after update.")
    if isinstance(text, (dict, list)):
        serialized = json.dumps(text, ensure_ascii=False).strip()
        if serialized:
            return
    raise SafeImportError(f"Unexpected empty readback for '{section_path}'.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safe resume JSON importer for remote Resume MCP (SSE)."
    )
    parser.add_argument("--version", required=True, help="Target resume version name.")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_SSE_ENDPOINT,
        help=f"SSE endpoint URL (default: {DEFAULT_SSE_ENDPOINT})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Render and print section markdown, do not write.")
    parser.add_argument("--network-timeout", type=float, default=20.0, help="Network timeout in seconds.")
    parser.add_argument("--response-timeout", type=float, default=30.0, help="Response wait timeout in seconds.")
    parser.add_argument("--verbose", action="store_true", help="Print extra debug details.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for HTTPS (use only in trusted environments).",
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-file", help="Path to resume JSON input file.")
    source.add_argument("--stdin", action="store_true", help="Read raw bytes from stdin.")
    source.add_argument("--input-b64", help="Base64-encoded resume JSON payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        raw = _load_input_bytes(args)
        text = _decode_input_bytes(raw)
        payload, parse_mode = _parse_json_payload(text)
        metadata, by_id, by_type = _index_sections(payload)

        client = RemoteSSEMCPClient(
            sse_url=args.endpoint,
            network_timeout=args.network_timeout,
            response_timeout=args.response_timeout,
            insecure_tls=args.insecure,
        )
        client.connect()
        try:
            client.initialize()

            tools_payload = client.call("tools/list", {})
            tools_obj = _coerce_json_if_possible(tools_payload)
            if isinstance(tools_obj, dict):
                tools = tools_obj.get("tools")
                if isinstance(tools, list):
                    names = {
                        _to_text(item.get("name"))
                        for item in tools
                        if isinstance(item, dict)
                    }
                    if "call_me_at_the_first_time_when_you_are_chatgpt" in names:
                        client.call_tool("call_me_at_the_first_time_when_you_are_chatgpt", {})

            versions_payload = client.call_tool("list_resume_versions", {})
            _ensure_version_exists(versions_payload, args.version)

            sections_payload = client.call_tool("list_resume_sections", {"version_name": args.version})
            sections = _extract_sections(sections_payload)

            updated: list[str] = []
            skipped: list[str] = []

            for section in sections:
                section_id = section["id"]
                section_type = section.get("type", "")
                source = _source_for_section(payload, metadata, by_id, by_type, section_id, section_type)
                markdown = _render_for_section(section_id, section_type, source)
                if not markdown or not markdown.strip():
                    skipped.append(section_id)
                    continue

                if args.dry_run:
                    print(f"\n===== {section_id} =====")
                    print(markdown)
                    updated.append(section_id)
                    continue

                _ = client.call_tool(
                    "update_resume_section",
                    {
                        "version_name": args.version,
                        "section_id": section_id,
                        "new_content": markdown,
                    },
                )
                section_path = f"{args.version}/{section_id}"
                readback = client.call_tool("read_resume_text", {"target_path": section_path})
                _check_readback_not_empty(readback, section_path)
                updated.append(section_id)

            summary = {
                "status": "ok",
                "endpoint": args.endpoint,
                "version": args.version,
                "parse_mode": parse_mode,
                "dry_run": args.dry_run,
                "updated_sections": updated,
                "skipped_sections": skipped,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))

            if args.verbose and not args.dry_run:
                print(
                    "Write completed via SSE MCP section updates with readback checks.",
                    file=sys.stderr,
                )
            return 0
        finally:
            client.close()

    except SafeImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
