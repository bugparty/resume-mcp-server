"""Tool-call logging and the persisted failure-event log behind /error-logs."""

from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse

from resume_platform.infrastructure.settings import get_settings

logger = logging.getLogger("resume_platform.mcp")

FAILURE_KINDS = ("exception", "error_response")
_RESULT_PREVIEW_CHARS = 500
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _writable_logs_dir() -> Path:
    try:
        logs_dir = Path(get_settings().logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "resume_mcp" / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class ErrorEventLog:
    """Append-only JSONL log of failed tool calls.

    The path is resolved on first use (not at import) so that importing the
    server has no filesystem side effects; tests may assign ``path`` directly.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _resolved_path(self) -> Path:
        if self.path is None:
            self.path = _writable_logs_dir() / "mcp_error_events.jsonl"
        return self.path

    def append(self, event: dict[str, Any]) -> None:
        path = self._resolved_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Failed to write MCP error event to %s", path)

    def read(self) -> tuple[list[dict[str, Any]], int]:
        """Return ``(events, number_of_unparseable_lines)``."""
        path = self._resolved_path()
        if not path.exists():
            return [], 0
        with self._lock:
            lines = path.read_text(encoding="utf-8").splitlines()
        events: list[dict[str, Any]] = []
        parse_errors = 0
        for line in filter(str.strip, lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            if isinstance(payload, dict):
                events.append(payload)
            else:
                parse_errors += 1
        return events, parse_errors


error_log = ErrorEventLog()

_logging_lock = threading.Lock()
_log_file: Path | None = None


def configure_logging() -> Path:
    """Attach console + file handlers to the package logger (idempotent)."""
    global _log_file
    with _logging_lock:
        if _log_file is not None:
            return _log_file
        log_file = _writable_logs_dir() / "mcp_server.log"
        package_logger = logging.getLogger("resume_platform")
        package_logger.setLevel(logging.INFO)
        formatter = logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        handlers: list[logging.Handler] = [logging.StreamHandler()]
        try:
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError:
            logger.warning("Cannot open log file %s; logging to console only", log_file)
        for handler in handlers:
            handler.setFormatter(formatter)
            package_logger.addHandler(handler)
        _log_file = log_file
        return log_file


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return repr(value)


def _error_payload(result: Any) -> dict[str, Any] | None:
    """Detect results that report failure in-band as ``{"error": ...}``."""
    payload = result
    if isinstance(result, str):
        try:
            payload = json.loads(result)
        except ValueError:
            return None
    if isinstance(payload, dict) and "error" in payload:
        return _to_jsonable(payload)
    return None


def _event(tool_name: str, kind: str, args: Any, kwargs: Any, elapsed: float, **extra):
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "failure_kind": kind,
        "args": _to_jsonable(args),
        "kwargs": _to_jsonable(kwargs),
        "execution_time_ms": int(elapsed * 1000),
        "error_type": None,
        "error_message": None,
        "traceback": None,
        **extra,
    }


def log_tool_call(func: Callable) -> Callable:
    """Log each call and record failures to :data:`error_log`."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        name = func.__name__
        started = time.perf_counter()
        logger.info("tool %s called with %s", name, _to_jsonable(kwargs or args))
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            error_log.append(
                _event(
                    name,
                    "exception",
                    args,
                    kwargs,
                    elapsed,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    traceback=traceback.format_exc(),
                )
            )
            logger.warning("tool %s failed after %.3fs: %s", name, elapsed, exc)
            raise
        elapsed = time.perf_counter() - started
        preview = str(result)
        if len(preview) > _RESULT_PREVIEW_CHARS:
            preview = preview[:_RESULT_PREVIEW_CHARS] + "..."
        logger.info("tool %s ok in %.3fs: %s", name, elapsed, preview)

        payload = _error_payload(result)
        if payload is not None:
            error_log.append(
                _event(
                    name,
                    "error_response",
                    args,
                    kwargs,
                    elapsed,
                    error_message=str(payload.get("error")),
                    result_payload=payload,
                )
            )
        return result

    return wrapper


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=400)


async def error_logs_endpoint(request: Request) -> JSONResponse:
    """``GET /error-logs?limit=&offset=&tool_name=&failure_kind=``"""
    query = request.query_params
    try:
        limit = int(query.get("limit", "50"))
    except ValueError:
        return _bad_request("limit must be an integer")
    if not 1 <= limit <= 500:
        return _bad_request("limit must be in range [1, 500]")
    try:
        offset = int(query.get("offset", "0"))
    except ValueError:
        return _bad_request("offset must be an integer")
    if offset < 0:
        return _bad_request("offset must be >= 0")
    tool_name = query.get("tool_name")
    failure_kind = query.get("failure_kind")
    if failure_kind and failure_kind not in FAILURE_KINDS:
        return _bad_request(f"failure_kind must be one of: {', '.join(FAILURE_KINDS)}")

    events, parse_errors = error_log.read()
    matching = [
        event
        for event in events
        if (not tool_name or event.get("tool_name") == tool_name)
        and (not failure_kind or event.get("failure_kind") == failure_kind)
    ]
    matching.sort(key=lambda event: str(event.get("timestamp", "")), reverse=True)
    return JSONResponse(
        {
            "total": len(matching),
            "limit": limit,
            "offset": offset,
            "items": matching[offset : offset + limit],
            "parse_errors": parse_errors,
            "log_file": str(error_log.path),
        }
    )
