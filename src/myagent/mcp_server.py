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
from pathlib import Path
import mimetypes
from typing import Union, Any, Callable
from functools import wraps
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Add the src directory to Python path for imports
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root / "src"))

from fastmcp import FastMCP

# Configure logging for MCP server
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# File handler for MCP tool calls
mcp_log_file = LOGS_DIR / "mcp_server.log"
file_handler = logging.FileHandler(mcp_log_file, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Console handler for real-time feedback
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


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
    from .settings import load_settings
    from .filesystem import init_filesystems
    from .tools import (
        list_resume_versions_tool,
        load_complete_resume_tool,
        load_resume_section_tool,
        update_resume_section_tool,
        analyze_jd_tool,
        create_new_version_tool,
        delete_resume_version_tool,
        update_main_resume_tool,
        list_modules_in_version_tool,
        tailor_section_for_jd_tool,
        read_jd_file_tool,
        summarize_resumes_to_index_tool,
        read_resume_summary_tool,
        render_resume_to_latex_tool,
        compile_resume_pdf_tool,
    )
except ImportError:
    from myagent.settings import load_settings
    from myagent.filesystem import init_filesystems
    from myagent.tools import (
        list_resume_versions_tool,
        load_complete_resume_tool,
        load_resume_section_tool,
        update_resume_section_tool,
        analyze_jd_tool,
        create_new_version_tool,
        delete_resume_version_tool,
        update_main_resume_tool,
        list_modules_in_version_tool,
        tailor_section_for_jd_tool,
        read_jd_file_tool,
        summarize_resumes_to_index_tool,
        read_resume_summary_tool,
        render_resume_to_latex_tool,
        compile_resume_pdf_tool,
    )

settings = None
def init():
    global logger, settings
    """Initialize settings and filesystems."""
    # Initialize filesystem before starting server
    logger.info("=" * 80)
    logger.info("Starting MCP Server for Resume Agent Tools")
    logger.info(f"Log file: {mcp_log_file}")
    logger.info("=" * 80)

    settings = load_settings()
    init_filesystems(settings.resume_fs_url, settings.jd_fs_url)

    logger.info("Filesystems initialized")
    logger.info("MCP Server ready to accept connections")
    logger.info("=" * 80 + "\n")

# Create FastMCP instance
mcp = FastMCP("Resume Agent Tools")
init()


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


@mcp.tool()
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
@mcp.tool()
@log_mcp_tool_call
def list_resume_versions() -> str:
    """Lists all available resume versions stored as YAML files."""
    return list_resume_versions_tool()


@mcp.tool()
@log_mcp_tool_call
def load_complete_resume(filename: str) -> str:
    """
    Renders the full resume as Markdown.

    Args:
        filename: Resume YAML filename (e.g., 'resume.yaml')
    """
    return load_complete_resume_tool(filename)


@mcp.tool()
@log_mcp_tool_call
def load_resume_section(module_path: str) -> str:
    """
    Loads the Markdown content of a specific resume section.

    Args:
        module_path: Version/section identifier (e.g., 'resume/summary')
    """
    return load_resume_section_tool(module_path)


@mcp.tool()
@log_mcp_tool_call
def update_resume_section(module_path: str, new_content: str) -> str:
    """
    Overwrite a resume section with new Markdown content.

    Args:
        module_path: Version/section identifier (e.g., 'resume/summary', 'resume/experience', 'resume/projects', 'resume/skills', 'resume/header')
        new_content: Replacement Markdown preserving headings and bullet lists
    
    Format Examples:
    
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
    
    Education Section (Raw format):
        ## Education
        **Master of Science in Computer Science**
        Stanford University | 2016 - 2018
        
        **Bachelor of Science in Computer Engineering**
        UC Berkeley | 2012 - 2016
    """
    return update_resume_section_tool(module_path, new_content)


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
def list_modules_in_version(filename: str) -> str:
    """
    Lists all section identifiers defined in a resume YAML file.

    Args:
        filename: Resume filename (e.g., 'resume.yaml')
    """
    return list_modules_in_version_tool(filename)


# Job Description Analysis Tools
@mcp.tool()
@log_mcp_tool_call
def analyze_jd(jd_text: str) -> str:
    """
    Analyzes job description text to extract key information.

    Args:
        jd_text: Job description text to analyze

    Returns:
        Structured analysis including job title, company, responsibilities, skills, etc.
    """
    return analyze_jd_tool(jd_text)


@mcp.tool()
@log_mcp_tool_call
def read_jd_file(filename: str) -> str:
    """
    Reads a job description file from the data/jd directory.

    Args:
        filename: JD filename (e.g., 'job1.txt'). Only .txt files are supported.
    """
    return read_jd_file_tool(filename)


@mcp.tool()
@log_mcp_tool_call
def tailor_section_for_jd(
    module_path: str, section_content: str, jd_analysis: str
) -> str:
    """
    Tailors the content of a specific resume section based on Job Description analysis.

    Args:
        module_path: Resume section path using 'version/section' format
        section_content: Current Markdown content of the section
        jd_analysis: The job description analysis result
    """
    return tailor_section_for_jd_tool(module_path, section_content, jd_analysis)


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


@mcp.tool()
@log_mcp_tool_call
def read_resume_summary() -> str:
    """
    Reads the lightweight resume summary YAML and returns it as text.
    """
    result = read_resume_summary_tool()
    return result.content


# Resume Format Documentation Tools
@mcp.tool()
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
def render_resume_pdf(version: str) -> str:
    """
    Render a resume version directly to PDF file.

    This function combines LaTeX generation and PDF compilation in one step
    and saves the PDF to the data/output directory with a meaningful filename.

    Args:
        version: Resume version name without extension (e.g., 'resume')

    Returns:
        Filesystem path to the generated PDF file in data/output directory
    """
    # First render to LaTeX
    latex_result = render_resume_to_latex_tool(version)
    latex_content = latex_result.latex

    # Then compile to PDF - the tool now saves to data/output directory
    pdf_result = compile_resume_pdf_tool(latex_content, version)
    return pdf_result.pdf_path


def main(transport="stdio", port=8000):
    """Main entry point for the MCP server."""
    if transport == "http":
        mcp.run(transport="http", port=port, log_level="DEBUG")
    else:
        mcp.run(log_level="DEBUG")


if __name__ == "__main__":
    # Default to HTTP server when run directly
    main(transport="http", port=8000)
