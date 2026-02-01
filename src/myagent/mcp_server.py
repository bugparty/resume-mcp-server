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
from typing import Union, Any, Callable
from functools import wraps
from enum import Enum
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from dotenv import load_dotenv
from fs.copy import copy_fs
from fs.osfs import OSFS


# Ensure src-based imports resolve when running via `fastmcp inspect`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path and SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))

# Load environment variables early so settings pick up overrides
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

from fastmcp import FastMCP

# Configure logging for MCP server
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def log_mcp_tool_call(func: Callable) -> Callable:
    """
    Decorator to log MCP tool calls with arguments and results.
    """

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
    from .settings import load_settings, get_settings
    from .filesystem import init_filesystems, get_output_fs
    from .s3_utils import upload_bytes_to_s3
    from .tools import (
        list_resume_versions_tool,
        load_complete_resume_tool,
        load_resume_section_tool,
        update_resume_section_tool,
        create_new_version_tool,
        delete_resume_version_tool,
        copy_resume_version_tool,
        update_main_resume_tool,
        list_modules_in_version_tool,
        summarize_resumes_to_index_tool,
        read_resume_summary_tool,
        render_resume_to_latex_tool,
        compile_resume_pdf_tool,
        submit_resume_pdf_job_tool,
        get_resume_pdf_job_status_tool,
        set_section_visibility_tool,
        set_section_order_tool,
        get_section_style_tool,
    )
except ImportError:
    from myagent.settings import load_settings, get_settings
    from myagent.filesystem import init_filesystems, get_output_fs
    from myagent.s3_utils import upload_bytes_to_s3
    from myagent.tools import (
        list_resume_versions_tool,
        load_complete_resume_tool,
        load_resume_section_tool,
        update_resume_section_tool,
        create_new_version_tool,
        delete_resume_version_tool,
        copy_resume_version_tool,
        update_main_resume_tool,
        list_modules_in_version_tool,
        summarize_resumes_to_index_tool,
        read_resume_summary_tool,
        render_resume_to_latex_tool,
        compile_resume_pdf_tool,
        submit_resume_pdf_job_tool,
        get_resume_pdf_job_status_tool,
        set_section_visibility_tool,
        set_section_order_tool,
        get_section_style_tool,
    )

def _initialize_logging() -> Path:
    settings = get_settings()
    logs_dir = settings.logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_path = logs_dir / "mcp_server.log"

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return log_path


mcp_log_file = _initialize_logging()
settings = load_settings()
init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

# Create FastMCP instance
mcp = FastMCP("Resume Agent Tools")


# Define server-level prompt to guide AI assistants
@mcp.prompt()
def resume_agent_prompt() -> list[dict]:
    """
    System prompt for the Resume Agent MCP Server.
    
    This prompt guides AI assistants on how to use this server effectively
    for resume management and job application optimization.
    """
    return [
        {
            "role": "system",
            "content": """You are a professional Resume Management Assistant powered by the Resume Agent MCP Server.

Your primary responsibilities include:
1. **Resume Version Management**: Help users create, manage, and organize multiple versions of their resumes
2. **Content Optimization**: Tailor resume content to match specific job descriptions
3. **Resume Rendering**: Generate professional PDF resumes from YAML data
4. **Job Description Analysis**: Analyze job postings to identify key requirements and keywords

Available Capabilities:
- List and load resume versions from the data directory
- Create new resume versions or update existing ones
- Analyze job descriptions (JD) and extract key requirements
- Update resume sections to match job requirements
- Render resumes to LaTeX and compile to PDF
- Manage resume summaries and indexes
- Read and compare multiple resume versions

Best Practices:
- Always list available resume versions before loading
- When tailoring resumes, analyze the JD first to understand requirements
- **IMPORTANT**: You CANNOT update the entire resume at once. You MUST update one section at a time using `update_resume_section`
- Only update specific sections (e.g., 'resume/summary', 'resume/experience', 'resume/skills', 'resume/projects')
- Never attempt to replace the complete resume YAML in a single operation
- Minimize repetitive confirmations—if the user has requested help across multiple sections, acknowledge once and proceed section-by-section without asking for permission each time (unless the user explicitly requests step-by-step approval)
- Keep resume content concise, professional, and achievement-focused
- Use action verbs and quantifiable results when possible
- Maintain consistent formatting across sections
- Save different versions for different job applications

Workflow Example:
1. User provides a job description → analyze_jd to extract requirements
2. List available resume versions → list_resume_versions
3. Load relevant sections → load_resume_section or load_complete_resume
4. Manually review and optimize content based on JD analysis
5. **Update ONE section at a time** → update_resume_section for each section (summary, experience, skills, etc.)
6. Repeat step 5 for other sections that need updates, narrating progress periodically without over-asking for confirmation
7. Generate PDF → render_resume_to_latex + compile_resume_pdf
    - The render_resume_pdf tool uploads the generated PDF to configured object storage and returns a dictionary with a time-limited `signed_url` and `filename`. Download the file using the signed URL when a local copy is required.

**Critical Reminder**: 
- The system does NOT support updating the entire resume in one call
- You must break down resume updates into individual section updates
- Each section update is a separate tool call to `update_resume_section`
- Common sections: 'resume/summary', 'resume/experience', 'resume/projects', 'resume/skills', 'resume/header'

Always be helpful, professional, and focused on creating compelling resume content that highlights the user's strengths."""
        }
    ]


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


# Global variable to store the data directory path
DATA_DIR = None


def get_data_dir():
    """Get the data directory path."""
    global DATA_DIR
    if DATA_DIR is None:
        # Get the project root directory (two levels up from this file)
        project_root = Path(__file__).resolve().parents[2]
        DATA_DIR = project_root / "data"
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
    data_dir = get_data_dir()
    file_path = data_dir / path

    # Security check: ensure the path is within data directory
    try:
        file_path = file_path.resolve()
        data_dir = data_dir.resolve()
        if not str(file_path).startswith(str(data_dir)):
            raise ValueError("Path outside data directory not allowed")
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid file path: {e}")

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
annotations=dict(readOnlyHint=True))
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

    data_dir = get_data_dir()
    target_dir = data_dir / path if path else data_dir

    # Security check: ensure the path is within data directory
    try:
        target_dir = target_dir.resolve()
        data_dir = data_dir.resolve()
        if not str(target_dir).startswith(str(data_dir)):
            raise ValueError("Path outside data directory not allowed")
    except (OSError, ValueError) as e:
        return json.dumps({"error": f"Invalid directory path: {e}"})

    if not target_dir.exists():
        return json.dumps({"error": f"Directory not found: {path}"})

    if not target_dir.is_dir():
        return json.dumps({"error": f"Path is not a directory: {path}"})

    try:
        items = []
        for item in sorted(target_dir.iterdir()):
            relative_path = str(item.relative_to(data_dir))
            item_info = {
                "name": item.name,
                "path": relative_path,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            }

            # Add MIME type for files
            if item.is_file():
                mime_type, _ = mimetypes.guess_type(str(item))
                item_info["mime_type"] = mime_type

            items.append(item_info)

        return json.dumps(
            {"path": path, "items": items, "total_items": len(items)}, indent=2
        )

    except Exception as e:
        return json.dumps({"error": f"Failed to list directory: {e}"})


# Resume Version Management Tools
@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def list_resume_versions() -> str:
    """Lists all available resume versions stored as YAML files.

    Returns:
        JSON string containing the version names and total count.
    """
    return list_resume_versions_tool()


@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def load_complete_resume(filename: str) -> str:
    """
    Renders the full resume as Markdown.

    Args:
        filename: Resume YAML filename (e.g., 'resume.yaml')
    """
    return load_complete_resume_tool(filename)


@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def get_resume_section(version_name: str, section_id: ResumeSectionId) -> str:
    """
    Load a specific section from a resume file.
    
    Args:
        version_name: Resume file name WITHOUT .yaml extension (e.g., 'resume')
        section_id: Section identifier to load (must be one of: header, summary, 
                   skills, experience, projects, education, custom)
    
    Returns:
        Markdown content of the requested section
        
    Example:
        get_resume_section(version_name="resume", section_id=ResumeSectionId.SUMMARY)
    """
    return load_resume_section_tool(f"{version_name}/{section_id.value}")


@mcp.tool()
@log_mcp_tool_call
def update_resume_section(
    version_name: str,
    section_id: ResumeSectionId,
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
        
    See get_resume_yaml_format() for content format examples.
    """
    return update_resume_section_tool(f"{version_name}/{section_id.value}", new_content)


@mcp.tool()
@log_mcp_tool_call
def set_section_visibility(version: str, section_id: str, enabled: bool = True) -> str:
    """
    Enable or disable rendering of a specific section in a resume version.

    Args:
        version: Resume version name (without .yaml)
        section_id: Section id to toggle (e.g., 'summary', 'experience')
        enabled: True to show, False to hide
    """
    try:
        result = set_section_visibility_tool(version, section_id, enabled)
        payload = {"version": version, "section_id": section_id, "enabled": enabled}
        try:
            payload.update(result if isinstance(result, dict) else {})
        except Exception:
            pass
        return json.dumps(payload)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
@log_mcp_tool_call
def set_section_order(version: str, order: list[str]) -> str:
    """
    Set the rendering order of sections for a resume version.

    Args:
        version: Resume version name (without .yaml)
        order: List of section ids in desired order; unknown ids are skipped and remaining sections are appended automatically.
    """
    try:
        result = set_section_order_tool(version, order)
        payload = {"version": version, "order": order}
        try:
            payload.update(result if isinstance(result, dict) else {})
        except Exception:
            pass
        return json.dumps(payload)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def get_section_style(version: str) -> str:
    """
    Get current section order and disabled flags for a resume version.

    Args:
        version: Resume version name (without .yaml)
    """
    try:
        result = get_section_style_tool(version)
        payload = {"version": version}
        try:
            payload.update(json.loads(result)) if isinstance(result, str) else payload.update(result)
        except Exception:
            payload["raw"] = result
        return json.dumps(payload)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
@log_mcp_tool_call
def create_new_version(new_version_name: str) -> str:
    """
    Creates a new resume version by copying the default YAML template.

    Args:
        new_version_name: The name for the new resume version (e.g., 'resume_for_google')
    """
    return create_new_version_tool(new_version_name)


@mcp.tool()
@log_mcp_tool_call
def delete_resume_version(version_name: str) -> str:
    """
    Permanently deletes a resume version.

    Args:
        version_name: The name of the resume version to delete (without .yaml extension)

    Note:
        - Cannot delete the base 'resume' version
        - This operation cannot be undone
        - Ensure you have backups if needed
    """
    return delete_resume_version_tool(version_name)


@mcp.tool()
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


@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def list_resume_sections(filename: str) -> str:
    """
    List all section identifiers available in a resume file.

    Args:
        filename: Resume file name (e.g., 'resume.yaml')
    
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
    return list_modules_in_version_tool(filename)

# Resume Summary and Index Tools
@mcp.tool()
@log_mcp_tool_call
def summarize_resumes_to_index() -> dict:
    """
    Aggregates resume metadata into resume_summary.yaml for quick scanning.

    Returns:
        Dictionary with yaml_path and message about the indexing process
    """
    result = summarize_resumes_to_index_tool()
    return {"yaml_path": result.yaml_path, "message": result.message}


@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def read_resume_summary() -> str:
    """
    Reads the lightweight resume summary YAML and returns it as text.
    """
    result = read_resume_summary_tool()
    return result.content


# Resume Format Documentation Tools
@mcp.tool(annotations=dict(readOnlyHint=True))
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
    import json
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

- type: entries
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

- type: entries
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

### 3. Entries Section (type: "entries")
- **Required fields**: `id`, `title`, `entries`
- **Purpose**: Experience, education, projects with structured data
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
- Don't mix section types (e.g., don't put `bullets` in `entries` section)
- Ensure all required fields are present for each section type
- Follow the exact structure shown in the schema
"""

    return documentation


# Resume Rendering Tools
@mcp.tool()
@log_mcp_tool_call
def render_resume_pdf(version: str) -> dict[str, str]:
    """
    Render a resume version directly to PDF file. **This is a WRITE tool** because it
    generates a new PDF under data/output.

    This function combines LaTeX generation and PDF compilation in one step,
    persists the PDF to the configured output filesystem, uploads the file to
    the configured S3-compatible storage, and returns a public download link
    for downstream clients.

    Args:
        version: Resume version name without extension (e.g., 'resume')

    Returns:
        Dictionary with keys:
        - `public_url`: Direct URL to download the uploaded PDF.
        - `filename`: Suggested filename (including `.pdf` extension) for the rendered resume.
        - `pdf_path`: Filesystem URI for the saved PDF.
        - `latex_assets_dir`: Optional directory containing LaTeX sources for debugging.
    """
    # First render to LaTeX
    latex_result = render_resume_to_latex_tool(version)
    latex_content = latex_result.latex

    # Then compile to PDF - the tool now saves to data/output directory
    pdf_result = compile_resume_pdf_tool(latex_content, version)
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


@mcp.tool()
@log_mcp_tool_call
def submit_resume_pdf_job(version: str) -> dict[str, str]:
    """
    Submit an async resume render+compile job.

    This tool renders LaTeX, uploads the LaTeX and assets bundle to S3, and
    enqueues a Celery job for PDF compilation. It returns job/task identifiers.
    """
    return submit_resume_pdf_job_tool(version).model_dump()


@mcp.tool(annotations=dict(readOnlyHint=True))
@log_mcp_tool_call
def get_resume_pdf_job_status(task_id: str) -> dict[str, str | None]:
    """
    Query the status of an async resume PDF job by Celery task id.
    """
    return get_resume_pdf_job_status_tool(task_id).model_dump()


@mcp.tool()
@log_mcp_tool_call
def render_resume_to_overleaf(version: str) -> dict[str, str]:
    """
    Render a resume version to a LaTeX project suitable for Overleaf import.

    This tool generates the LaTeX sources without compiling them, bundles the
    assets into a ZIP archive, uploads the archive to S3-compatible storage, and
    returns an Overleaf import URL.

    Args:
        version: Resume version name without extension (e.g., 'resume')

    Returns:
        Dictionary with keys:
        - `overleaf_url`: Direct link that opens the project in Overleaf via snip URI.
        - `public_url`: Public URL of the uploaded ZIP archive.
        - `filename`: Name of the ZIP archive stored in output storage.
        - `zip_path`: Filesystem URI for the saved ZIP archive.
        - `latex_assets_dir`: Directory containing the LaTeX sources for debugging.
    """

    latex_result = render_resume_to_latex_tool(version)
    latex_content = latex_result.latex

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{version}_{timestamp}_overleaf.zip"
    latex_dir_name = f"{version}_{timestamp}_latex"

    template_root = Path(__file__).resolve().parents[2] / "templates"
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

    overleaf_url = f"https://www.overleaf.com/docs?snip_uri={quote(public_url, safe='')}&engine=xelatex"

    response: dict[str, str] = {
        "overleaf_url": overleaf_url,
        "public_url": public_url,
        "filename": zip_filename,
        "zip_path": zip_path,
        "latex_assets_dir": latex_assets_dir,
    }
    return response


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
    logger.info(f"Log file: {mcp_log_file}")
    logger.info("=" * 80)

    
    logger.info("Filesystems initialized")
    logger.info("MCP Server ready to accept connections")
    logger.info("=" * 80 + "\n")

    if transport == "http":
        mcp.run(transport="http", port=port, log_level="DEBUG")
    else:
        mcp.run()


if __name__ == "__main__":
    main(transport="http", port=8000)
