#!/usr/bin/env python3
"""
FastMCP Server for Resume Agent Tools

This module exposes all the resume management tools from tools.py as MCP tools,
allowing them to be used by MCP clients like Claude Desktop.
"""

import sys
import os
import json
import logging
import time
import io
import shutil
import tempfile
import zipfile
from pathlib import Path
import mimetypes
from urllib.parse import quote
from enum import Enum
from typing import Union, Callable, Any
from functools import wraps
from contextlib import asynccontextmanager
try:
    import boto3  # Backward-compatible test patch target.
except Exception:
    boto3 = None
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import BaseRoute
from dotenv import load_dotenv
from fs.copy import copy_fs
from fs.osfs import OSFS
import uvicorn
import fastmcp


# Ensure repo-root-based paths resolve when running via `fastmcp inspect`
PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path and SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))

# Load environment variables early so settings pick up overrides
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

from fastmcp import FastMCP
from fastmcp.server.http import set_http_request
from fastmcp.server.context import reset_transport, set_transport

# Configure logging for MCP server
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ResumeSectionId(str, Enum):
    """Enumeration of valid resume section identifiers.
    
    Available sections:
        HEADER: Personal information (name, contact, links)
        SUMMARY: Professional summary/bio
        SKILLS: Technical skills organized by category
        EXPERIENCE: Work history
        PROJECTS: Personal or open-source projects
        EDUCATION: Academic background
        CUSTOM: Custom/free-form content (e.g., languages, interests)
    """
    
    HEADER = "header"
    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    CUSTOM = "raw"  # Maps to 'raw' type in YAML schema


def log_mcp_tool_call(func: Callable) -> Callable:
    """
    Decorator to log MCP tool calls with arguments and results.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = time.time()

        # Log the call with arguments
        logger.info(f"=== MCP TOOL CALL: {tool_name} ===")

        # Log positional arguments
        if args:
            logger.info(f"Positional args: {args}")

        # Log keyword arguments
        if kwargs:
            logger.info(
                f"Keyword args: {json.dumps(kwargs, ensure_ascii=False, indent=2)}"
            )

        try:
            # Execute the function
            result = func(*args, **kwargs)

            # Calculate execution time
            execution_time = time.time() - start_time

            # Log the result (truncate if too long)
            result_str = str(result)
            if len(result_str) > 500:
                logger.info(f"Result (truncated): {result_str[:500]}...")
            else:
                logger.info(f"Result: {result_str}")

            logger.info(f"Execution time: {execution_time:.3f}s")
            logger.info(f"=== END: {tool_name} ===\n")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error in {tool_name}: {str(e)}", exc_info=True)
            logger.info(f"Execution time (failed): {execution_time:.3f}s")
            logger.info(f"=== END (ERROR): {tool_name} ===\n")
            raise

    return wrapper




# Try relative import first, fall back to absolute import
try:
    from resume_platform.infrastructure.settings import load_settings, get_settings
    from resume_platform.infrastructure.filesystem import (
        init_filesystems,
        get_resume_fs,
        get_jd_fs,
        get_output_fs,
        is_initialized,
    )
    from resume_platform.infrastructure.s3_utils import upload_bytes_to_s3
    from resume_platform.tools import (
        list_resume_versions_tool,
        load_complete_resume_tool,
        get_resume_section_tool,
        read_resume_text_tool,
        update_resume_section_tool,
        replace_resume_text_tool,
        insert_resume_text_tool,
        delete_resume_text_tool,
        create_new_version_tool,
        delete_resume_version_tool,
        copy_resume_version_tool,
        update_main_resume_tool,
        list_modules_in_version_tool,
        render_resume_to_latex_tool,
        compile_resume_pdf_tool,
        set_section_visibility_tool,
        set_section_order_tool,
        get_resume_layout_tool,
        build_vector_index_tool,
        search_resume_entries_tool,
        get_vector_index_status_tool,
    )
except ImportError:
    from resume_platform.infrastructure.settings import load_settings, get_settings
    from resume_platform.infrastructure.filesystem import (
        init_filesystems,
        get_resume_fs,
        get_jd_fs,
        get_output_fs,
        is_initialized,
    )
    from resume_platform.infrastructure.s3_utils import upload_bytes_to_s3
    from resume_platform.tools import (
        list_resume_versions_tool,
        load_complete_resume_tool,
        get_resume_section_tool,
        read_resume_text_tool,
        update_resume_section_tool,
        replace_resume_text_tool,
        insert_resume_text_tool,
        delete_resume_text_tool,
        create_new_version_tool,
        delete_resume_version_tool,
        copy_resume_version_tool,
        update_main_resume_tool,
        list_modules_in_version_tool,
        render_resume_to_latex_tool,
        compile_resume_pdf_tool,
        set_section_visibility_tool,
        set_section_order_tool,
        get_resume_layout_tool,
        build_vector_index_tool,
        search_resume_entries_tool,
        get_vector_index_status_tool,
    )

def _initialize_logging() -> Path:
    default_logs_dir = PROJECT_ROOT / "logs"
    settings = None
    try:
        settings = get_settings()
    except Exception:
        settings = None

    raw_logs_dir = getattr(settings, "logs_dir", None)
    if isinstance(raw_logs_dir, Path):
        logs_dir = raw_logs_dir
    elif isinstance(raw_logs_dir, str) and raw_logs_dir.strip():
        logs_dir = Path(raw_logs_dir)
    else:
        logs_dir = default_logs_dir

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        logs_dir = Path(tempfile.gettempdir()) / "resume_mcp" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

    log_path = logs_dir / "mcp_server.log"

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.handlers.clear()

    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return log_path


mcp_log_file = _initialize_logging()

def _ensure_server_filesystems_initialized() -> None:
    if is_initialized():
        return

    settings = None
    try:
        settings = load_settings()
    except Exception:
        settings = None

    resume_fs_url = getattr(settings, "resume_fs_url", None)
    jd_fs_url = getattr(settings, "jd_fs_url", None)

    if not (isinstance(resume_fs_url, str) and resume_fs_url.strip()):
        resume_fs_url = str(PROJECT_ROOT / "data" / "resumes")
    if not (isinstance(jd_fs_url, str) and jd_fs_url.strip()):
        jd_fs_url = str(PROJECT_ROOT / "data" / "jd")

    try:
        init_filesystems(resume_fs_url, jd_fs_url)
    except Exception as exc:
        allow_fallback = (
            os.getenv("RESUME_ALLOW_MEM_FS_FALLBACK", "").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        logger.exception(
            "Failed to initialize filesystems. resume_fs_url=%s jd_fs_url=%s",
            resume_fs_url,
            jd_fs_url,
        )
        if allow_fallback:
            logger.warning(
                "RESUME_ALLOW_MEM_FS_FALLBACK is enabled; falling back to mem:// filesystems."
            )
            init_filesystems("mem://", "mem://")
            return
        raise RuntimeError(
            "Filesystem initialization failed. Check RESUME_FS_URL/JD_FS_URL and S3 credentials. "
            "Set RESUME_ALLOW_MEM_FS_FALLBACK=true only for temporary debugging."
        ) from exc


_ensure_server_filesystems_initialized()

# Create FastMCP instance
mcp = FastMCP("Resume Agent Tools")


def _route_signature(route: BaseRoute) -> tuple[str, tuple[str, ...], str]:
    path = getattr(route, "path", repr(route))
    methods = tuple(sorted(getattr(route, "methods", []) or ()))
    return path, methods, type(route).__name__


def _dedupe_routes(routes: list[BaseRoute]) -> list[BaseRoute]:
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    result: list[BaseRoute] = []
    for route in routes:
        signature = _route_signature(route)
        if signature in seen:
            continue
        seen.add(signature)
        result.append(route)
    return result


def _cors_origins() -> list[str]:
    raw = os.getenv("MCP_CORS_ALLOW_ORIGINS", "*")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["*"]


class _DualTransportMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        transport_type = (
            "sse"
            if path == "/sse" or path.startswith("/messages/")
            else "streamable-http"
        )
        transport_token = set_transport(transport_type)
        try:
            with set_http_request(Request(scope)):
                await self.app(scope, receive, send)
        finally:
            reset_transport(transport_token)


def _build_dual_http_app() -> Starlette:
    sse_app = mcp.http_app(transport="sse")
    streamable_app = mcp.http_app(transport="http")
    routes = _dedupe_routes([*sse_app.routes, *streamable_app.routes])

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with streamable_app.lifespan(streamable_app):
            yield

    app = Starlette(routes=routes, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    app.add_middleware(_DualTransportMiddleware)
    return app


def _run_http_server(port: int) -> None:
    app = _build_dual_http_app()
    config = uvicorn.Config(
        app,
        host=fastmcp.settings.host,
        port=port,
        log_level=fastmcp.settings.log_level.lower(),
        timeout_graceful_shutdown=0,
        lifespan="on",
        ws="websockets-sansio",
    )
    server = uvicorn.Server(config)
    server.run()


# Define server-level prompt to guide AI assistants
@mcp.prompt()
def resume_agent_prompt() -> str:
    """
    System prompt for the Resume Agent MCP Server.
    
    This prompt guides AI assistants on how to use this server effectively
    for resume management and job application optimization.
    """
    return """You are a professional Resume Management Assistant powered by the Resume Agent MCP Server.

Your primary responsibilities include:
1. **Resume Version Management**: Help users create, manage, and organize multiple versions of their resumes
2. **Content Optimization**: Tailor resume content to match specific job descriptions
3. **Resume Rendering**: Generate professional PDF resumes
4. **Job Description Analysis**: Analyze job postings to identify key requirements and keywords
5. **Semantic Search**: Search experience and project entries with vector similarity

Available Capabilities:
- List and load resume versions from the data directory
- Create new resume versions or update existing ones
- Analyze job descriptions (JD) and extract key requirements
- Update resume sections to match job requirements
- Render resumes to LaTeX and compile to PDF
- Manage resume summaries and indexes
- Build and query semantic vector index for experience/project entries
- Read and compare multiple resume versions

Best Practices:
- Always list available resume versions before loading
- When tailoring resumes, analyze the JD first to understand requirements
- Prefer `read_resume_text` plus `replace_resume_text` / `insert_resume_text` / `delete_resume_text` for localized edits
- You may edit either one section (`version/section`) or the whole resume editable text view (`version`)
- Whole-resume text edits must preserve the existing top-level `##` block structure
- Never attempt to replace the complete resume YAML in a single operation
- Minimize repetitive confirmations—if the user has requested help across multiple sections, acknowledge once and proceed section-by-section without asking for permission each time (unless the user explicitly requests step-by-step approval)
- Keep resume content concise, professional, and achievement-focused
- Use action verbs and quantifiable results when possible
- Maintain consistent formatting across sections
- Save different versions for different job applications
- After section updates are complete, update `position` in header section so it matches the final resume focus and JD target role

Workflow Example:
1. User provides a job description → analyze_jd to extract requirements
2. List available resume versions → list_resume_versions
3. Load relevant sections/text → load_resume_section, read_resume_text, or load_complete_resume
4. Manually review and optimize content based on JD analysis
5. Apply localized text edits with replace/insert/delete tools, or use update_resume_section for full section rewrites
6. Repeat step 5 for other sections that need updates, narrating progress periodically without over-asking for confirmation
7. Before finalizing or generate pdf, update header(for job title) and skills( tech skills keywords) sections to the role implied by the updated resume content and JD
8. Generate PDF → render_resume_to_latex + compile_resume_pdf
    - The render_resume_pdf tool uploads the generated PDF to configured object storage and returns a dictionary with a time-limited `signed_url` and `filename`. Download the file using the signed URL when a local copy is required.


**Critical Reminder**:
- The system does NOT support replacing the entire resume YAML in one call
- Prefer localized text edits when only a small change is needed
- Whole-resume text edits must preserve top-level block structure
- Common sections: 'resume/summary', 'resume/experience', 'resume/projects', 'resume/skills', 'resume/header'

**Section Markdown Format Reference** (for update_resume_section new_content):

Header Section:
    ## Header
    first_name: John
    last_name: Doe
    position: Senior Software Engineer
    address: San Francisco, CA
    mobile: +1-234-567-8900
    email: john.doe@example.com
    github: github.com/johndoe
    linkedin: linkedin.com/in/johndoe

Summary Section:
    ## Summary
    - 8+ years of experience in full-stack development and cloud architecture
    - Expert in Python, JavaScript, and distributed systems
    - Led teams of 5-10 engineers to deliver scalable products

Skills Section:
    ## Skills
    - Programming: Python, JavaScript, Go, SQL
    - Cloud Platforms: AWS, GCP, Docker, Kubernetes
    - Tools & Practices: Git, Jenkins, Terraform, Agile/Scrum
    - Databases: PostgreSQL, MongoDB, Redis

Experience Section:
    ## Experience
    ### Software Engineer — TechCorp Inc (San Francisco, CA) | Jan 2020 - Present
    - Developed microservices using Python and Go
    - Led team of 5 engineers in agile sprints
    - Improved system performance by 40%

    ### Junior Developer — StartupXYZ (Remote) | Jun 2018 - Dec 2019
    - Built REST APIs with Node.js and Express
    - Implemented CI/CD pipelines using Jenkins

Projects Section:
    ## Projects
    ### E-Commerce Platform — Personal Project (GitHub) | 2023
    - Built full-stack web app with React and Django
    - Integrated Stripe payment processing
    - Deployed on AWS with Docker and Kubernetes

    ### Machine Learning Pipeline — University Research | 2022
    - Developed data processing pipeline for NLP tasks
    - Achieved 95% accuracy on sentiment analysis

Education Section:
    ## Education
    ### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA

    ### Bachelor of Science in Computer Engineering | Stanford University | 2012 - 2016 | Palo Alto, CA

Always be helpful, professional, and focused on creating compelling resume content that highlights the user's strengths."""

@mcp.tool(annotations=dict(readOnlyHint=True))
def call_me_at_the_first_time_when_you_are_chatgpt():
    """
    REQUIRED first-call handshake tool for ChatGPT clients.

    If the caller is ChatGPT, it MUST call this tool before invoking any
    other MCP tool for the first time in a session.
    This call records the initial connection and returns the server prompt
    used to bootstrap behavior.
    """
    logger.info("chatgpt has made the first call to read the prompts.")
    return resume_agent_prompt()

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


# Global variable to store the data directory path
DATA_DIR = None


def get_data_dir():
    """Get the data directory path."""
    global DATA_DIR
    if DATA_DIR is None:
        DATA_DIR = PROJECT_ROOT / "data"
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


@mcp.resource("data://{path}")
async def read_data_file(path: str) -> Union[str, bytes]:
    """
    Read files from the data directory.

    Args:
        path: Relative path within the data directory

    Returns:
        File content as string for text files, bytes for binary files
    """
    data_dir = get_data_dir().resolve()
    file_path = (data_dir / path).resolve()

    if not file_path.is_relative_to(data_dir):
        raise ValueError("Path outside data directory not allowed")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    # Determine if file should be read as text or binary
    mime_type, _ = mimetypes.guess_type(str(file_path))

    # Read as text for common text formats
    if (mime_type and mime_type.startswith("text/")) or file_path.suffix.lower() in [
        ".yaml",
        ".yml",
        ".json",
        ".md",
        ".txt",
        ".tex",
        ".py",
        ".js",
        ".html",
        ".css",
        ".xml",
    ]:
        return file_path.read_text(encoding="utf-8")
    else:
        # Read as binary for other formats (PDFs, images, etc.)
        return file_path.read_bytes()


@mcp.tool(
annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def list_data_directory(path: str = "") -> str:
    """
    List contents of the data directory or a subdirectory within it.

    Args:
        path: Relative path within the data directory (empty string for root)

    Returns:
        JSON string containing directory listing with file/folder info
    """
    import json

    data_dir = get_data_dir().resolve()
    target_dir = (data_dir / path).resolve() if path else data_dir

    if not target_dir.is_relative_to(data_dir):
        raise ValueError("Path outside data directory not allowed")
    if not target_dir.exists() and path == "":
        target_dir.mkdir(parents=True, exist_ok=True)
    if not target_dir.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    items = []
    for item in sorted(target_dir.iterdir()):
        relative_path = str(item.relative_to(data_dir))
        item_info = {
            "name": item.name,
            "path": relative_path,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        }
        if item.is_file():
            mime_type, _ = mimetypes.guess_type(str(item))
            item_info["mime_type"] = mime_type
        items.append(item_info)

    return json.dumps({"path": path, "items": items, "total_items": len(items)}, indent=2)


def _safe_listdir_summary(fs_obj: Any, path: str = ".", sample_size: int = 20) -> dict[str, Any]:
    try:
        entries = fs_obj.listdir(path)
        sorted_entries = sorted(entries)
        return {
            "ok": True,
            "path": path,
            "count": len(sorted_entries),
            "sample": sorted_entries[:sample_size],
        }
    except Exception as exc:
        return {
            "ok": False,
            "path": path,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


def _safe_yaml_walk_summary(fs_obj: Any, sample_size: int = 20) -> dict[str, Any]:
    try:
        yaml_paths = list(fs_obj.walk.files(filter=["*.yaml"]))
        versions = sorted(
            {
                path.rsplit("/", 1)[-1][:-5]
                for path in yaml_paths
                if path.rsplit("/", 1)[-1].endswith(".yaml")
            }
        )
        return {
            "ok": True,
            "yaml_path_count": len(yaml_paths),
            "yaml_paths_sample": yaml_paths[:sample_size],
            "version_count": len(versions),
            "versions_sample": versions[:sample_size],
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


def _fs_backend_summary(fs_obj: Any) -> dict[str, str]:
    cls = fs_obj.__class__
    return {
        "class_name": cls.__name__,
        "module": cls.__module__,
    }


@mcp.tool(
annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def diagnose_filesystems() -> str:
    """Diagnose MCP filesystem state and resume version discovery behavior.

    Returns:
        JSON string with active settings, backend types, directory summaries,
        and list_resume_versions output for quick troubleshooting.
    """
    settings = None
    try:
        settings = get_settings()
    except Exception as exc:
        settings = {"error": str(exc), "error_type": type(exc).__name__}

    payload: dict[str, Any] = {
        "initialized": is_initialized(),
        "settings": {
            "resume_fs_url": getattr(settings, "resume_fs_url", None),
            "jd_fs_url": getattr(settings, "jd_fs_url", None),
        }
        if not isinstance(settings, dict)
        else settings,
        "env_hints": {
            "RESUME_FS_URL": os.getenv("RESUME_FS_URL"),
            "RESUME_FS_UR": os.getenv("RESUME_FS_UR"),
            "JD_FS_URL": os.getenv("JD_FS_URL"),
            "RESUME_ALLOW_MEM_FS_FALLBACK": os.getenv("RESUME_ALLOW_MEM_FS_FALLBACK"),
        },
    }

    try:
        resume_fs = get_resume_fs()
        payload["resume_fs"] = {
            "backend": _fs_backend_summary(resume_fs),
            "top_level": _safe_listdir_summary(resume_fs, "."),
            "yaml_walk": _safe_yaml_walk_summary(resume_fs),
        }
    except Exception as exc:
        payload["resume_fs"] = {
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    try:
        jd_fs = get_jd_fs()
        payload["jd_fs"] = {
            "backend": _fs_backend_summary(jd_fs),
            "top_level": _safe_listdir_summary(jd_fs, "."),
        }
    except Exception as exc:
        payload["jd_fs"] = {
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    try:
        output_fs = get_output_fs()
        payload["output_fs"] = {
            "backend": _fs_backend_summary(output_fs),
            "top_level": _safe_listdir_summary(output_fs, "."),
        }
    except Exception as exc:
        payload["output_fs"] = {
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    try:
        payload["list_resume_versions"] = json.loads(list_resume_versions_tool())
    except Exception as exc:
        payload["list_resume_versions"] = {
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    return json.dumps(payload, ensure_ascii=False, indent=2)


# Resume Version Management Tools
@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def list_resume_versions() -> str:
    """Lists all available resume versions stored as YAML files.

    Returns:
        JSON string containing the version names and total count.
    """
    return list_resume_versions_tool()


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def load_complete_resume(version_name: str) -> str:
    """
    Renders the full resume as Markdown.

    Args:
        version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')
    """
    return load_complete_resume_tool(version_name)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def get_resume_section(version_name: str, section_id: str) -> str:
    """
    Load a specific section from a resume file.
    
    Args:
        version_name: Resume file name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier to load (must be one of: header, summary, 
                   skills, experience, projects, education, custom)
    
    Returns:
        Markdown content of the requested section
        
    Example:
        get_resume_section(version_name="resume", section_id="summary")
    """
    return get_resume_section_tool(version_name, section_id)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def read_resume_text(target_path: str) -> str:
    """
    Read editable resume markdown for a whole resume view or a single section.

    Args:
        target_path: Either 'version' for the whole resume text view or 'version/section'
    """
    return read_resume_text_tool(target_path)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def replace_resume_text(target_path: str, old_text: str, new_text: str) -> str:
    """
    Replace one exact text snippet in a resume text view.

    Args:
        target_path: Either 'version' or 'version/section'
        old_text: Exact snippet to replace; must match once
        new_text: Replacement text
    """
    return replace_resume_text_tool(target_path, old_text, new_text)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def insert_resume_text(
    target_path: str,
    new_text: str,
    position: str,
    anchor_text: str | None = None,
) -> str:
    """
    Insert text into a resume text view using a semantic position or anchor.

    Args:
        target_path: Either 'version' or 'version/section'
        new_text: Text to insert
        position: One of 'start', 'end', 'before', 'after'
        anchor_text: Required for before/after and must match once
    """
    return insert_resume_text_tool(target_path, new_text, position, anchor_text)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def delete_resume_text(target_path: str, old_text: str) -> str:
    """
    Delete one exact text snippet from a resume text view.

    Args:
        target_path: Either 'version' or 'version/section'
        old_text: Exact snippet to delete; must match once
    """
    return delete_resume_text_tool(target_path, old_text)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def read_resume_section_text(version_name: str, section_id: str) -> str:
    """
    Read editable markdown text for a single section using explicit section coordinates.

    Args:
        version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier (e.g., 'summary', 'experience')
    """
    target_path = f"{version_name}/{section_id}"
    return read_resume_text_tool(target_path)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def replace_resume_section_text(
    version_name: str,
    section_id: str,
    old_text: str,
    new_text: str,
) -> str:
    """
    Replace one exact snippet in a single resume section using explicit section coordinates.

    Args:
        version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier (e.g., 'summary', 'experience')
        old_text: Exact snippet to replace; must match once
        new_text: Replacement text
    """
    target_path = f"{version_name}/{section_id}"
    return replace_resume_text_tool(target_path, old_text, new_text)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def insert_resume_section_text(
    version_name: str,
    section_id: str,
    new_text: str,
    position: str,
    anchor_text: str | None = None,
) -> str:
    """
    Insert text into a single resume section using explicit section coordinates.

    Args:
        version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier (e.g., 'summary', 'experience')
        new_text: Text to insert
        position: One of 'start', 'end', 'before', 'after'
        anchor_text: Required for before/after and must match once
    """
    target_path = f"{version_name}/{section_id}"
    return insert_resume_text_tool(target_path, new_text, position, anchor_text)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def delete_resume_section_text(version_name: str, section_id: str, old_text: str) -> str:
    """
    Delete one exact snippet from a single resume section using explicit section coordinates.

    Args:
        version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier (e.g., 'summary', 'experience')
        old_text: Exact snippet to delete; must match once
    """
    target_path = f"{version_name}/{section_id}"
    return delete_resume_text_tool(target_path, old_text)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def update_resume_section(
    version_name: str,
    section_id: str,
    new_content: str
) -> str:
    """
    Update a specific section in a resume file with new Markdown content.
    
    Args:
        version_name: Resume file name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier to update (must be one of: header, summary,
                   skills, experience, projects, education, custom)
        new_content: New Markdown content for the section
    
    Returns:
        Success or error message
        
    Important:
        - Input must be in Markdown format
        - Cannot update entire resume at once
        - Must update ONE section at a time
        
        ### Machine Learning Pipeline — University Research | 2022
        - Developed data processing pipeline for NLP tasks
        - Achieved 95% accuracy on sentiment analysis

    Education Section:
        ## Education
        ### Master of Science in Computer Science | Stanford University | 2016 - 2018 | Palo Alto, CA

        ### Bachelor of Science in Computer Engineering | Stanford University | 2012 - 2016 | Palo Alto, CA

    See get_resume_yaml_format() for content format examples.
    """
    module_path = f"{version_name}/{section_id}"
    return update_resume_section_tool(module_path, new_content)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def set_section_visibility(
    version_name: str, section_id: str, enabled: bool = True
) -> str:
    """
    Enable or disable rendering of a specific section in a resume version.

    Args:
        version: Resume version name (without .yaml)
        section_id: Section id to toggle (e.g., 'summary', 'experience')
        enabled: True to show, False to hide
    """
    return set_section_visibility_tool(version_name, section_id, enabled)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def set_section_order(version_name: str, order: list[str]) -> str:
    """
    Set the rendering order of sections for a resume version.

    Args:
        version: Resume version name (without .yaml)
        order: List of section ids in desired order; unknown ids are skipped and remaining sections are appended automatically.
    """
    return set_section_order_tool(version_name, order)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def get_section_style(version: str) -> str:
    """
    Get current section order and disabled flags for a resume version.

    Args:
        version: Resume version name (without .yaml)
    """
    return get_resume_layout_tool(version)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def create_new_version(new_version_name: str) -> str:
    """
    Creates a new resume version.

    Args:
        new_version_name: The name for the new resume version (e.g., 'resume_for_google')
    """
    return create_new_version_tool(new_version_name)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def delete_resume_version(version_name: str) -> str:
    """
    Permanently deletes a resume version.

    Args:
        version_name: The name of the resume version to delete (without .yaml extension)

    Note:
        - Cannot delete the base 'resume' version
        - This operation cannot be undone
    """
    return delete_resume_version_tool(version_name)


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def copy_resume_version(source_version: str, target_version: str) -> str:
    """
    Copies an existing resume version to a new version.

    Args:
        source_version: The name of the source resume version to copy from (without .yaml extension)
        target_version: The name of the target resume version to copy to (without .yaml extension)

    Note:
        - The source version must exist
        - The target version must not already exist
    """
    return copy_resume_version_tool(source_version, target_version)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def list_resume_sections(version_name: str) -> str:
    """
    List all section identifiers available in a resume file.

    Args:
        version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')
    
    Returns:
        JSON string containing section identifiers and their types
        
    Example output:
        {
            "sections": [
                {"id": "header", "type": "header"},
                {"id": "summary", "type": "summary"},
                {"id": "skills", "type": "skills"},
                {"id": "experience", "type": "entries"},
                {"id": "projects", "type": "entries"},
                {"id": "education", "type": "entries"},
                {"id": "additional", "type": "raw"}
            ],
            "total": 7
        }
    """
    return list_modules_in_version_tool(version_name)



@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=False))
@log_mcp_tool_call
def build_vector_index(force_rebuild: bool = False) -> str:
    """
    Build or refresh vector index for resume experience/project entries.

    Args:
        force_rebuild: When true, recompute embeddings for all indexed chunks.
    """
    return build_vector_index_tool(force_rebuild)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def search_resume_entries(
    query: str,
    entry_type: str = "all",
    chunk_level: str = "entry",
    top_k: int = 5,
) -> str:
    """
    Semantic vector search over experience/projects entries.

    Args:
        query: Search query string
        entry_type: Filter by 'experience', 'projects', or 'all'
        chunk_level: Search granularity, 'entry' or 'bullet'
        top_k: Number of matches to return
    """
    return search_resume_entries_tool(query, entry_type, chunk_level, top_k)


@mcp.tool(annotations=dict(readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False))
@log_mcp_tool_call
def get_vector_index_status() -> str:
    """
    Get vector index freshness and collection statistics.
    """
    return get_vector_index_status_tool()


# Resume Format Documentation Tools
@mcp.tool(annotations=dict(readOnlyHint=True,
        openWorldHint=False,
        idempotentHint=True))
@log_mcp_tool_call
def get_resume_yaml_format() -> str:
    """
    Returns comprehensive documentation about the Resume YAML format including schema and examples.

    This function provides:
    1. The JSON schema that validates resume YAML files
    2. A complete example of a properly formatted resume YAML
    3. Detailed explanations of each section type

    Use this before calling update_main_resume to understand the required YAML structure.
    """
    from pathlib import Path

    # Get the schema content
    project_root = Path(__file__).resolve().parents[2]
    schema_path = project_root / "schemas" / "resume_schema.json"

    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_content = f.read()
    else:
        schema_content = "Schema file not found"

    # Create a comprehensive example
    example_yaml = """source: resume.tex
metadata:
  first_name: John
  last_name: Doe
  position: Software Engineer
  address: San Francisco, CA, USA
  mobile: (+1) 555-123-4567
  email: john.doe@example.com
  github: johndoe
  linkedin: johndoe
sections:
- type: summary
  id: summary
  title: Summary
  bullets:
  - "**5+ years of experience** in full-stack development with expertise in **Python**, **JavaScript**, and **React**."
  - "Strong background in **cloud technologies** including **AWS**, **Docker**, and **Kubernetes**."
  - "Passionate about building scalable, maintainable systems and contributing to open-source projects."

- type: skills
  id: skills
  title: Technical Skills
  groups:
  - category: Programming Languages
    items:
    - Python
    - JavaScript
    - TypeScript
    - Java
  - category: Frameworks & Libraries
    items:
    - React
    - Django
    - FastAPI
    - Node.js
  - category: DevOps & Cloud
    items:
    - AWS
    - Docker
    - Kubernetes
    - CI/CD

- type: experience
  id: experience
  title: Professional Experience
  entries:
  - title: Senior Software Engineer
    organization: Tech Company Inc.
    location: San Francisco, CA
    period: Jan 2022 - Present
    bullets:
    - "Led development of microservices architecture serving **1M+ daily users**"
    - "Implemented **CI/CD pipelines** reducing deployment time by 60%"
    - "Mentored junior developers and conducted technical interviews"
  - title: Software Engineer
    organization: StartupXYZ
    location: San Francisco, CA
    period: Jun 2019 - Dec 2021
    bullets:
    - "Built full-stack web applications using **React** and **Python/Django**"
    - "Optimized database queries resulting in **40% performance improvement**"

- type: education
  id: education
  title: Education
  entries:
  - title: B.S. in Computer Science
    organization: University of California
    location: Berkeley, CA
    period: Sep 2015 - May 2019
    bullets:
    - "Relevant Coursework: Data Structures, Algorithms, Software Engineering"
    - "GPA: 3.8/4.0"

- type: raw
  id: additional
  title: Additional Information
  content: |
    **Languages**: English (Native), Spanish (Conversational)
    **Interests**: Open source contribution, Machine Learning, Rock climbing"""

    documentation = f"""# Resume YAML Format Documentation

## Overview
Resume YAML files must conform to a strict schema. They cannot be Markdown files - only valid YAML with specific structure.

## JSON Schema
The following JSON schema defines the validation rules:

```json
{schema_content}
```

## Section Types

### 1. Summary Section (type: "summary")
- **Required fields**: `id`, `title`, `bullets`
- **Purpose**: Brief professional overview
- **bullets**: Array of strings describing key qualifications

### 2. Skills Section (type: "skills") 
- **Required fields**: `id`, `title`, `groups`
- **Purpose**: Technical skills organized by category
- **groups**: Array of objects with `category` and `items` fields

### 3. Experience/Projects/Education Section (type: "experience" | "projects" | "education")
- **Required fields**: `id`, `title`, `entries`
- **Purpose**: Structured timeline content (work, projects, education)
- **entries**: Array of objects with `title`, `organization`, `location`, `period`, `bullets`

### 4. Raw Section (type: "raw")
- **Required fields**: `id`, `title`, `content`
- **Purpose**: Free-form content like additional information
- **content**: String with raw text content

## Complete Example

```yaml
{example_yaml}
```

## Important Notes

1. **Schema Validation**: All YAML files are validated against the JSON schema
2. **Required Fields**: Each section type has specific required fields
3. **ID Constraints**: Special validation for 'experience' and 'projects' IDs
4. **No Markdown**: Input must be valid YAML, not Markdown
5. **Bullets Format**: Use Markdown formatting within bullet strings for emphasis

## Common Mistakes to Avoid

- Don't use Markdown file format - only YAML
- Don't mix section types (e.g., don't put `bullets` in an `experience` section)
- Ensure all required fields are present for each section type
- Follow the exact structure shown in the schema
"""

    return documentation


# Resume Rendering Tools
@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=True))
@log_mcp_tool_call
def render_resume_pdf(version_name: str) -> dict[str, str]:
    """
    Render a resume version directly to PDF file. **This is a WRITE tool** because it
    generates a new PDF under data/output.

    This function combines LaTeX generation and PDF compilation in one step,
    persists the PDF to the configured output filesystem, uploads the file to
    the configured S3-compatible storage, and returns a public download link
    for downstream clients.

    Args:
        version_name: Resume version name without extension (e.g., 'resume')

    Returns:
        Dictionary with keys:
        - `public_url`: Direct URL to download the uploaded PDF.
        - `filename`: Suggested filename (including `.pdf` extension) for the rendered resume.
        - `pdf_path`: Filesystem URI for the saved PDF.
        - `latex_assets_dir`: Optional directory containing LaTeX sources for debugging.
    """
    # First render to LaTeX
    latex_result = render_resume_to_latex_tool(version_name)
    latex_content = latex_result.latex

    # Then compile to PDF - the tool now saves to data/output directory
    pdf_result = compile_resume_pdf_tool(latex_content, version_name)
    output_fs = get_output_fs()

    # Extract filename from returned resource path (e.g., data://resumes/output/foo.pdf)
    pdf_path = pdf_result.pdf_path
    filename = pdf_path.split("/")[-1]

    try:
        with output_fs.open(filename, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
    except Exception as exc:
        logger.error("Failed to read generated PDF '%s': %s", filename, exc, exc_info=True)
        raise RuntimeError(f"Failed to read generated PDF '{filename}'") from exc

    public_url, _ = upload_bytes_to_s3(
        pdf_bytes,
        filename,
        "application/pdf",
        "resume PDF",
    )

    response: dict[str, str] = {
        "public_url": public_url,
        "filename": filename,
    }
    if pdf_result.latex_assets_dir:
        response["latex_assets_dir"] = pdf_result.latex_assets_dir
    response["pdf_path"] = pdf_result.pdf_path
    return response


@mcp.tool(annotations=dict(readOnlyHint=False,
        idempotentHint=False,
        openWorldHint=True))
@log_mcp_tool_call
def render_resume_to_overleaf(version_name: str) -> dict[str, str]:
    """
    Render a resume version to a LaTeX project suitable for Overleaf import.

    This tool generates the LaTeX sources without compiling them, bundles the
    assets into a ZIP archive, uploads the archive to S3-compatible storage, and
    returns an Overleaf import URL.

    Args:
        version_name: Resume version name without extension (e.g., 'resume')

    Returns:
        Dictionary with keys:
        - `overleaf_url`: Direct link that opens the project in Overleaf via snip URI.
        - `public_url`: Public URL of the uploaded ZIP archive.
        - `filename`: Name of the ZIP archive stored in output storage.
        - `zip_path`: Filesystem URI for the saved ZIP archive.
        - `latex_assets_dir`: Directory containing the LaTeX sources for debugging.
    """

    latex_result = render_resume_to_latex_tool(version_name)
    latex_content = latex_result.latex

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{version_name}_{timestamp}_overleaf.zip"
    latex_dir_name = f"{version_name}_{timestamp}_latex"

    template_root = PROJECT_ROOT / "templates"
    output_fs = get_output_fs()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        tex_path = tmp_path / "main.tex"
        tex_path.write_text(latex_content, encoding="utf-8")

        essential_files = ["awesome-cv.cls", "profile.png"]
        for filename in essential_files:
            src_file = template_root / filename
            if src_file.exists():
                shutil.copy(src_file, tmp_path / filename)

        fonts_src = template_root / "fonts"
        if fonts_src.exists() and fonts_src.is_dir():
            shutil.copytree(fonts_src, tmp_path / "fonts")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for path in tmp_path.rglob("*"):
                if path.is_file():
                    zip_file.write(path, arcname=str(path.relative_to(tmp_path)))

        zip_bytes = zip_buffer.getvalue()

        if output_fs.exists(latex_dir_name):
            output_fs.removetree(latex_dir_name)
        latex_subfs = output_fs.makedir(latex_dir_name, recreate=True)
        try:
            with OSFS(tmp_path) as tmp_fs:
                copy_fs(tmp_fs, latex_subfs)
        finally:
            latex_subfs.close()

    output_fs.writebytes(zip_filename, zip_bytes)

    zip_path = f"data://resumes/output/{zip_filename}"
    latex_assets_dir = f"data://resumes/output/{latex_dir_name}"

    public_url, _ = upload_bytes_to_s3(
        zip_bytes,
        zip_filename,
        "application/zip",
        "resume Overleaf package",
    )

    overleaf_url = f"https://www.overleaf.com/docs?snip_uri={quote(public_url, safe='')}"

    response: dict[str, str] = {
        "overleaf_url": overleaf_url,
        "public_url": public_url,
        "filename": zip_filename,
        "zip_path": zip_path,
        "latex_assets_dir": latex_assets_dir,
    }
    return response


# Backward-compatibility for tests/callers that use StructuredTool-style access.
render_resume_pdf.fn = render_resume_pdf
render_resume_to_overleaf.fn = render_resume_to_overleaf


def _resolve_transport(default_transport: str, default_port: int) -> tuple[str, int]:
    env_transport = (
        os.getenv("FASTMCP_TRANSPORT")
        or os.getenv("MCP_TRANSPORT")
        or os.getenv("TRANSPORT")
    )
    transport = (env_transport or default_transport).lower()
    if transport not in {"http", "stdio"}:
        logger.warning(
            "Unknown transport '%s' specified via environment; falling back to '%s'",
            transport,
            default_transport,
        )
        transport = default_transport

    env_port = (
        os.getenv("FASTMCP_PORT")
        or os.getenv("MCP_PORT")
        or os.getenv("PORT")
    )
    port = default_port
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            logger.warning(
                "Invalid port value '%s'; using default %d",
                env_port,
                default_port,
            )
            port = default_port

    return transport, port


def main(transport="stdio", port=8000):
    """Main entry point for the MCP server."""
    transport, port = _resolve_transport(transport, port)

    # Initialize filesystem before starting server
    logger.info("=" * 80)
    logger.info("Starting MCP Server for Resume Agent Tools")
    logger.info(f"Transport: {transport}")
    if transport == "http":
        logger.info(f"Port: {port}")
        logger.info("HTTP MCP endpoints: /mcp (streamable HTTP), /sse, /messages/")
    logger.info(f"Log file: {mcp_log_file}")
    logger.info("=" * 80)

    
    logger.info("Filesystems initialized")
    logger.info("MCP Server ready to accept connections")
    logger.info("=" * 80 + "\n")

    if transport == "http":
        _run_http_server(port)
    else:
        mcp.run()


if __name__ == "__main__":
    main(transport="http", port=8000)
