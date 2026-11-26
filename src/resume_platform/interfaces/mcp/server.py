"""FastMCP server assembly and entry points.

Importing this module builds the ``mcp`` object (tool/prompt/route
registration only) but does not touch settings, filesystems or log files;
:func:`start_runtime` does that, once, from each entry point. See
``docs/adr/0001-composition-root-and-runtime-lifecycle.md``.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable

import fastmcp
import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.context import reset_transport, set_transport
from fastmcp.server.http import set_http_request
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import BaseRoute

from resume_platform.infrastructure.bootstrap import bootstrap
from resume_platform.infrastructure.filesystem import (
    get_jd_fs,
    get_output_fs,
    get_resume_fs,
)
from resume_platform.paths import PROJECT_ROOT
from resume_platform.vector_search import mark_index_stale

from . import telemetry
from .prompts import RESUME_AGENT_PROMPT
from .tools import TOOLS, ToolSpec

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = {".yaml", ".yml", ".json", ".md", ".txt", ".tex"}


def start_runtime() -> None:
    """Load ``.env``, configure logging and bootstrap settings + storage.

    Idempotent. Filesystem-init failures propagate: refusing to start beats
    silently serving from throwaway storage.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    telemetry.configure_logging()
    bootstrap()


def _with_index_invalidation(spec: ToolSpec) -> Callable[..., Any]:
    @wraps(spec.fn)
    def wrapper(*args, **kwargs):
        result = spec.fn(*args, **kwargs)
        mark_index_stale(spec.fn.__name__)
        return result

    return wrapper


def build_server() -> FastMCP:
    server = FastMCP("Resume Agent Tools", instructions=RESUME_AGENT_PROMPT)

    for spec in TOOLS:
        fn = _with_index_invalidation(spec) if spec.writes_resume else spec.fn
        server.tool(
            telemetry.log_tool_call(fn),
            name=spec.fn.__name__,
            annotations=spec.annotations,
        )

    @server.prompt()
    def resume_agent_prompt() -> str:
        """Usage guide for assistants working with this server."""
        return RESUME_AGENT_PROMPT

    @server.resource("data://{path*}")
    def read_data_file(path: str) -> str | bytes:
        """Read a stored file: ``resumes/<name>``, ``resumes/output/<name>``
        (rendered PDFs, Overleaf zips) or ``jd/<name>``."""
        if path.startswith("resumes/output/"):
            fs_obj, inner = get_output_fs(), path.removeprefix("resumes/output/")
        elif path.startswith("resumes/"):
            fs_obj, inner = get_resume_fs(), path.removeprefix("resumes/")
        elif path.startswith("jd/"):
            fs_obj, inner = get_jd_fs(), path.removeprefix("jd/")
        else:
            raise ValueError("Path must start with resumes/, resumes/output/ or jd/")
        if ".." in inner.split("/"):
            raise ValueError("Parent directory references are not allowed")
        if not fs_obj.isfile(inner):
            raise FileNotFoundError(f"File not found: {path}")
        mime_type, _ = mimetypes.guess_type(inner)
        suffix = os.path.splitext(inner)[1].lower()
        if suffix in TEXT_SUFFIXES or (mime_type or "").startswith("text/"):
            return fs_obj.readtext(inner, encoding="utf-8")
        return fs_obj.readbytes(inner)

    @server.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    server.custom_route("/error-logs", methods=["GET"])(telemetry.error_logs_endpoint)
    return server


mcp = build_server()


# --- HTTP transport -----------------------------------------------------------


def _dedupe_routes(routes: list[BaseRoute]) -> list[BaseRoute]:
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    result: list[BaseRoute] = []
    for route in routes:
        key = (
            getattr(route, "path", repr(route)),
            tuple(sorted(getattr(route, "methods", None) or ())),
            type(route).__name__,
        )
        if key not in seen:
            seen.add(key)
            result.append(route)
    return result


def _cors_origins() -> list[str]:
    raw = os.getenv("MCP_CORS_ALLOW_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()] or ["*"]


class _DualTransportMiddleware:
    """Tell FastMCP which transport a request belongs to (SSE vs streamable)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        is_sse = path == "/sse" or path.startswith("/messages/")
        token = set_transport("sse" if is_sse else "streamable-http")
        try:
            with set_http_request(Request(scope)):
                await self.app(scope, receive, send)
        finally:
            reset_transport(token)


def create_http_app() -> Starlette:
    """ASGI app serving both streamable HTTP (``/mcp``) and SSE (``/sse``).

    Usable directly as an ASGI factory, so it assembles the runtime itself.
    """
    start_runtime()
    sse_app = mcp.http_app(transport="sse")
    streamable_app = mcp.http_app(transport="http")

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with streamable_app.lifespan(streamable_app):
            yield

    app = Starlette(
        routes=_dedupe_routes([*sse_app.routes, *streamable_app.routes]),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    app.add_middleware(_DualTransportMiddleware)
    return app


def resolve_transport(default_transport: str, default_port: int) -> tuple[str, int]:
    """Apply ``MCP_TRANSPORT`` / ``MCP_PORT`` (and aliases) env overrides."""
    transport = (
        os.getenv("FASTMCP_TRANSPORT")
        or os.getenv("MCP_TRANSPORT")
        or os.getenv("TRANSPORT")
        or default_transport
    ).lower()
    if transport not in {"http", "stdio"}:
        logger.warning("Unknown transport %r; using %r", transport, default_transport)
        transport = default_transport

    port = default_port
    raw_port = os.getenv("FASTMCP_PORT") or os.getenv("MCP_PORT") or os.getenv("PORT")
    if raw_port:
        try:
            port = int(raw_port)
        except ValueError:
            logger.warning("Invalid port %r; using %d", raw_port, default_port)
    return transport, port


def main(transport: str = "stdio", port: int = 8000) -> None:
    """Run the server over stdio (default) or HTTP."""
    transport, port = resolve_transport(transport, port)
    start_runtime()
    logger.info("Starting Resume MCP server (transport=%s)", transport)
    if transport == "http":
        logger.info("HTTP endpoints on port %d: /mcp, /sse, /messages/", port)
        uvicorn.run(
            create_http_app(),
            host=fastmcp.settings.host,
            port=port,
            log_level=fastmcp.settings.log_level.lower(),
            timeout_graceful_shutdown=0,
            lifespan="on",
            ws="websockets-sansio",
        )
    else:
        mcp.run()


def cli() -> None:
    """Console-script entry point: ``resume-mcp [--transport http] [--port N]``."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the Resume MCP server.")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(transport=args.transport, port=args.port)


if __name__ == "__main__":
    cli()
