from pathlib import Path
import shutil
import tempfile
import json

from fs.copy import copy_fs
from fs.osfs import OSFS

from langchain_core.messages import HumanMessage
from resume_platform.infrastructure.llm_config import get_thinking_llm
from resume_platform.resume.views import (
    load_resume_section,
    read_resume_text,
    list_modules_in_version,
    load_complete_resume,
)
from resume_platform.resume.editing import (
    tailor_section_for_jd,
    summarize_resumes_to_index,
    read_resume_summary,
    update_resume_section,
    replace_resume_text,
    insert_resume_text,
    delete_resume_text,
    update_main_resume,
    create_new_version,
)
from .resume.repository import find_resume_versions, set_section_visibility, set_section_order, get_section_style
from .resume_renderer import render_resume, compile_tex_remote
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from resume_platform.infrastructure.filesystem import get_jd_fs, get_output_fs
from .vector_search import (
    mark_index_stale,
    build_index,
    search_entries,
    get_index_status,
)


# --- Pydantic Models for Tool Input ---
class EmptyInput(BaseModel):
    """Empty input model for tools that don't require parameters."""
    pass

class TextFilenameInput(BaseModel):
    filename: str = Field(..., description="The resume filename, e.g., 'resume.yaml'")

class ResumeSectionInput(BaseModel):
    module_path: str = Field(..., description="Resume section path using 'version/section', e.g., 'resume/summary'")

class ResumeTextTargetInput(BaseModel):
    target_path: str = Field(
        ...,
        description="Editable resume text target, either 'version' for the whole resume view or 'version/section' for one section.",
    )

class UpdateResumeSectionInput(BaseModel):
    module_path: str = Field(..., description="Resume section path using 'version/section', e.g., 'resume/summary'")
    new_content: str = Field(..., description="Updated Markdown content for the section")

class ReplaceResumeTextInput(BaseModel):
    target_path: str = Field(
        ...,
        description="Editable resume text target, either 'version' or 'version/section'.",
    )
    old_text: str = Field(..., description="Exact text snippet to replace. Must match exactly once.")
    new_text: str = Field(..., description="Replacement text.")

class InsertResumeTextInput(BaseModel):
    target_path: str = Field(
        ...,
        description="Editable resume text target, either 'version' or 'version/section'.",
    )
    new_text: str = Field(..., description="Text to insert.")
    position: str = Field(
        ...,
        description="Insertion position: 'start', 'end', 'before', or 'after'.",
    )
    anchor_text: str | None = Field(
        default=None,
        description="Required when position is 'before' or 'after'. Must match exactly once.",
    )

class DeleteResumeTextInput(BaseModel):
    target_path: str = Field(
        ...,
        description="Editable resume text target, either 'version' or 'version/section'.",
    )
    old_text: str = Field(..., description="Exact text snippet to delete. Must match exactly once.")

class AnalyzeJDInput(BaseModel):
    jd_text: str = Field(..., description="The full text of the Job Description to analyze")

class CreateNewVersionInput(BaseModel):
    new_version_name: str = Field(..., description="The name for the new resume version, e.g., 'resume_for_google'")

class DeleteResumeVersionInput(BaseModel):
    version_name: str = Field(..., description="The name of the resume version to delete, e.g., 'resume_for_google'")

class CopyResumeVersionInput(BaseModel):
    source_version: str = Field(..., description="The name of the source resume version to copy from, e.g., 'resume'")
    target_version: str = Field(..., description="The name of the target resume version to copy to, e.g., 'resume_for_google'")

class UpdateMainResumeInput(BaseModel):
    file_name: str = Field(..., description="The resume filename (e.g., 'resume.yaml')")
    file_content: str = Field(..., description="Full YAML content representing the resume")

class TailorSectionForJDInput(BaseModel):
    module_path: str = Field(..., description="Resume section path using 'version/section'")
    section_content: str = Field(..., description="Current Markdown content of the section")
    jd_analysis: str = Field(..., description="The job description analysis result")

class ReadJDInput(BaseModel):
    filename: str = Field(..., description="The filename of the JD file to read, e.g., 'job1.txt'")

class SummarizeResumesToIndexOutput(BaseModel):
    yaml_path: str = Field(..., description="The path to the generated YAML file.")
    message: str = Field(..., description="Summary of the indexing process.")

class ReadResumeSummaryOutput(BaseModel):
    content: str = Field(..., description="The content of the lightweight resume summary YAML file.")


class RenderResumeInput(BaseModel):
    version: str = Field(..., description="Resume version name without extension, e.g., 'resume'")


class RenderResumeOutput(BaseModel):
    latex: str = Field(..., description="Generated LaTeX content for the resume")


class CompileResumeInput(BaseModel):
    tex_content: str = Field(..., description="Full LaTeX content to compile")
    version_name: str = Field(default="resume", description="Version name to use in filename")


class CompileResumeOutput(BaseModel):
    pdf_path: str = Field(..., description="Filesystem path to the generated PDF")
    latex_assets_dir: str | None = Field(
        default=None,
        description="Filesystem path to the directory containing LaTeX sources and assets used for compilation.",
    )


class BuildVectorIndexInput(BaseModel):
    force_rebuild: bool = Field(
        default=False,
        description="Whether to force re-embedding all chunks instead of using cache.",
    )


class SearchResumeEntriesInput(BaseModel):
    query: str = Field(..., description="Semantic search query text.")
    entry_type: str = Field(
        default="all",
        description="Filter by section type: 'experience', 'projects', or 'all'.",
    )
    chunk_level: str = Field(
        default="entry",
        description="Search granularity: 'entry' or 'bullet'.",
    )
    top_k: int = Field(default=5, description="Maximum number of matches to return.")

# --- Tool Implementation Functions ---
def _is_success_message(result: str) -> bool:
    return isinstance(result, str) and result.strip().startswith("[Success]")


def _mark_stale_after_success(result: str, reason: str) -> None:
    if _is_success_message(result):
        mark_index_stale(reason)


def list_resume_versions_tool() -> str:
    """Return the available resume versions as a JSON payload."""
    versions = find_resume_versions()
    if not versions:
        return json.dumps(
            {"error": "No resume versions found.", "versions": [], "total": 0},
            ensure_ascii=False,
        )
    return json.dumps(
        {"versions": versions, "total": len(versions)}, ensure_ascii=False
    )

def load_resume_section_tool(module_path: str) -> str:
    """
    Load the Markdown content of a resume section using 'version/section' syntax.
    """
    return load_resume_section(module_path)

def read_resume_text_tool(target_path: str) -> str:
    """
    Read editable markdown text for a whole resume view or one section.
    """
    return read_resume_text(target_path)

def update_resume_section_tool(module_path: str, new_content: str) -> str:
    """
    Updates the Markdown content of a resume section.
    Input:
    - module_path: Version/section identifier
    - new_content: Markdown to replace the section body while preserving headings/bullets
    """
    result = update_resume_section(module_path, new_content)
    _mark_stale_after_success(result, "update_resume_section")
    return result

def replace_resume_text_tool(target_path: str, old_text: str, new_text: str) -> str:
    """
    Replace one exact text snippet in a resume text view.
    """
    result = replace_resume_text(target_path, old_text, new_text)
    _mark_stale_after_success(result, "replace_resume_text")
    return result

def insert_resume_text_tool(
    target_path: str,
    new_text: str,
    position: str,
    anchor_text: str | None = None,
) -> str:
    """
    Insert text into a resume text view using a semantic position or anchor.
    """
    result = insert_resume_text(target_path, new_text, position, anchor_text)
    _mark_stale_after_success(result, "insert_resume_text")
    return result

def delete_resume_text_tool(target_path: str, old_text: str) -> str:
    """
    Delete one exact text snippet from a resume text view.
    """
    result = delete_resume_text(target_path, old_text)
    _mark_stale_after_success(result, "delete_resume_text")
    return result

def analyze_jd_tool(jd_text: str) -> str:
    """
    Analyzes job description text to extract key information.
    Input:
    - jd_text: Job description text
    Function: Extracts and structures the following information:
    - Job Title
    - Company Name
    - Key Responsibilities
    - Required Skills
    - Required Experience
    - Educational Requirements
    - Keywords
    - Additional Notes
    Output: Structured analysis in a clear format
    """
    # Add a check for empty or very short input
    if not jd_text or len(jd_text.strip()) < 20: # Consider input less than 20 chars as potentially invalid/empty
        return """JD Analysis:
**Job Title:** N/A
**Company:** N/A
**Key Responsibilities:** N/A
**Required Skills:** N/A
**Required Experience:** N/A
**Educational Requirements:** N/A
**Keywords:** N/A
**Notes:** N/A (No valid Job Description provided)"""

    prompt = f"""
    Please analyze the following Job Description and extract the key information. Structure the output clearly.

    Job Description:
    ---
    {jd_text}
    ---

    Extract the following:
    - **Job Title:**
    - **Company:**
    - **Key Responsibilities:** (Summarize main duties)
    - **Required Skills:** (List essential technical and soft skills)
    - **Required Experience:** (Mention years of experience, specific domains, tools, etc.)
    - **Educational Requirements:** (If specified)
    - **Keywords:** (List important nouns and technologies)
    - **Notes:** (Other things You think it can make my resume standout)

    If you cannot find information for a specific field based *only* on the provided Job Description text, fill it with N/A.
    Provide the output as a structured text summary.
    """
    try:
        response = get_thinking_llm().invoke([HumanMessage(content=prompt)])
        analysis = response.content if hasattr(response, 'content') else str(response)
        # Ensure the response starts correctly, prepend if necessary (basic safety check)
        if not analysis.strip().startswith("**Job Title:**"):
             return f"JD Analysis:\n{analysis}"
        else:
             # If LLM already provided the structure, just add the header
             return f"JD Analysis:\n{analysis}"
    except Exception as e:
        return f"[Error] Failed to analyze JD with LLM: {e}"

def create_new_version_tool(new_version_name: str) -> str:
    """Create a new resume YAML version by copying the base template."""
    result = create_new_version(new_version_name)
    _mark_stale_after_success(result, "create_new_version")
    return result

def delete_resume_version_tool(version_name: str) -> str:
    """
    Delete a resume version permanently.
    Input:
    - version_name: The name of the resume version to delete (without .yaml extension)
    Note: This operation cannot be undone. Ensure you have backups if needed.
    """
    from resume_platform.infrastructure.filesystem import get_resume_fs
    
    # Validate input
    version_name = version_name.strip()
    if not version_name:
        return "[Error] Version name cannot be empty."
    
    # Check if it's the base resume
    if version_name == "resume":
        return "[Error] Cannot delete the base resume version 'resume'. This is the main template."
    
    # Get filename and filesystem
    filename = f"{version_name}.yaml"
    resume_fs = get_resume_fs()
    
    # Check if version exists
    if not resume_fs.exists(filename):
        return f"[Error] Resume version '{version_name}' does not exist."
    
    try:
        # Delete the file
        resume_fs.remove(filename)
        result = f"[Success] Resume version '{version_name}' has been deleted successfully."
        _mark_stale_after_success(result, "delete_resume_version")
        return result
    except Exception as e:
        return f"[Error] Failed to delete resume version '{version_name}': {str(e)}"

def copy_resume_version_tool(source_version: str, target_version: str) -> str:
    """
    Copy a resume version to a new version.
    Input:
    - source_version: The name of the source resume version to copy from (without .yaml extension)
    - target_version: The name of the target resume version to copy to (without .yaml extension)
    """
    from resume_platform.infrastructure.filesystem import get_resume_fs
    
    # Validate input
    source_version = source_version.strip()
    target_version = target_version.strip()
    
    if not source_version:
        return "[Error] Source version name cannot be empty."
    if not target_version:
        return "[Error] Target version name cannot be empty."
    if source_version == target_version:
        return "[Error] Source and target version names must be different."
    
    # Get filenames and filesystem
    source_filename = f"{source_version}.yaml"
    target_filename = f"{target_version}.yaml"
    resume_fs = get_resume_fs()
    
    # Check if source version exists
    if not resume_fs.exists(source_filename):
        return f"[Error] Source resume version '{source_version}' does not exist."
    
    # Check if target version already exists
    if resume_fs.exists(target_filename):
        return f"[Error] Target resume version '{target_version}' already exists. Delete it first or choose a different name."
    
    try:
        # Copy the file
        content = resume_fs.readtext(source_filename)
        resume_fs.writetext(target_filename, content)
        result = f"[Success] Resume version '{source_version}' has been copied to '{target_version}' successfully."
        _mark_stale_after_success(result, "copy_resume_version")
        return result
    except Exception as e:
        return f"[Error] Failed to copy resume version '{source_version}' to '{target_version}': {str(e)}"

def list_modules_in_version_tool(filename: str) -> str:
    """
    List all section identifiers present in the given resume YAML file.
    """
    return list_modules_in_version(filename)

def tailor_section_for_jd_tool(module_path: str, section_content: str, jd_analysis: str) -> str:
    """
    Customizes a resume section based on job description analysis.
    Input:
    - module_path: Full path to the module
    - section_content: Current content of the section
    - jd_analysis: Analysis results of the job description
    Function: Optimizes the resume section content based on job description analysis
    """
    # Use the helper function from resume_loader.py
    return tailor_section_for_jd(module_path, section_content, jd_analysis)

def update_main_resume_tool(file_name: str, file_content: str) -> str:
    """
    Update the content of a main resume file.
    Input:
    - file_name: Resume filename
    - file_content: New resume content
    Note: When modifying submodules after creating a new version, update their include paths here first
    """
    result = update_main_resume(file_name, file_content)
    _mark_stale_after_success(result, "update_main_resume")
    return result

def read_jd_file_tool(filename: str) -> str:
    """
    Reads a job description file from the JD filesystem.
    Input:
    - filename: JD filename (e.g., 'job1.txt')
    Function: Reads and returns the content of the specified job description file
    Note: Only .txt files are supported
    """
    if not filename.endswith('.txt'):
        return "[Error] Only .txt files are supported."

    try:
        jd_fs = get_jd_fs()
        
        if not jd_fs.exists(filename):
            return f"[Error] JD file '{filename}' not found."

        content = jd_fs.readtext(filename, encoding='utf-8')
        return content
    except Exception as e:
        return f"[Error] Failed to read JD file: {str(e)}"

def load_complete_resume_tool(filename: str) -> str:
    """
    Render the full resume as Markdown for the requested YAML file.
    """
    return load_complete_resume(filename)

def summarize_resumes_to_index_tool() -> SummarizeResumesToIndexOutput:
    """Generate a lightweight resume_summary.yaml for quick scanning."""
    result = summarize_resumes_to_index()
    return SummarizeResumesToIndexOutput(**result)


def read_resume_summary_tool() -> ReadResumeSummaryOutput:
    """Read the content of the lightweight resume summary YAML."""
    result = read_resume_summary()
    return ReadResumeSummaryOutput(**result)


def set_section_visibility_tool(version: str, section_id: str, enabled: bool = True) -> str:
    """Enable or disable a section by updating style.section_disabled."""
    try:
        result = set_section_visibility(version, section_id, enabled)
        mark_index_stale("set_section_visibility")
        return json.dumps({"version": version, "section_id": section_id, "enabled": enabled, **result})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def set_section_order_tool(version: str, order: list[str]) -> str:
    """Set preferred section ordering for rendering."""
    try:
        result = set_section_order(version, order)
        mark_index_stale("set_section_order")
        return json.dumps({"version": version, "order": order, **result})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def get_section_style_tool(version: str) -> str:
    """Get current section order and disabled map for a version."""
    try:
        result = get_section_style(version)
        return json.dumps({"version": version, **result})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def render_resume_to_latex_tool(version: str) -> RenderResumeOutput:
    """Render a resume version to LaTeX string."""
    latex = render_resume(version)
    return RenderResumeOutput(latex=latex)


def compile_resume_pdf_tool(tex_content: str, version_name: str = "resume") -> CompileResumeOutput:
    """Compile LaTeX content into a PDF using the remote compile service."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        template_root = Path(__file__).resolve().parents[2] / "templates"
        
        # Only copy the essential files needed for LaTeX compilation
        essential_files = [
            "awesome-cv.cls",  # Document class file
            "profile.png",     # Profile image (if exists)
        ]
        
        # Copy essential files
        for filename in essential_files:
            src_file = template_root / filename
            if src_file.exists():
                shutil.copy(src_file, tmp_path / filename)
        
        # Copy fonts directory (required by awesome-cv.cls)
        fonts_src = template_root / "fonts"
        if fonts_src.exists() and fonts_src.is_dir():
            shutil.copytree(fonts_src, tmp_path / "fonts")

        pdf_path = compile_tex_remote(tex_path)

        # Generate filename with version name and timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{version_name}_{timestamp}.pdf"
        latex_dir_name = f"{version_name}_{timestamp}_latex"

        # Use output filesystem to save the PDF and LaTeX assets
        output_fs = get_output_fs()
        with open(pdf_path, "rb") as src_file:
            output_fs.writebytes(output_filename, src_file.read())

        # Export LaTeX build directory for debugging
        if output_fs.exists(latex_dir_name):
            output_fs.removetree(latex_dir_name)
        latex_subfs = output_fs.makedir(latex_dir_name, recreate=True)
        try:
            with OSFS(tmp_path) as tmp_fs:
                copy_fs(tmp_fs, latex_subfs)
        finally:
            latex_subfs.close()

    return CompileResumeOutput(
        pdf_path="data://resumes/output/" + output_filename,
        latex_assets_dir="data://resumes/output/" + latex_dir_name,
    )


def build_vector_index_tool(force_rebuild: bool = False) -> str:
    """Build or refresh vector index for resume experience/projects entries."""
    result = build_index(force_rebuild=force_rebuild)
    return json.dumps(result, ensure_ascii=False)


def search_resume_entries_tool(
    query: str,
    entry_type: str = "all",
    chunk_level: str = "entry",
    top_k: int = 5,
) -> str:
    """Semantic search across indexed resume experience/project entries."""
    result = search_entries(
        query=query,
        entry_type=entry_type,
        chunk_level=chunk_level,
        top_k=top_k,
    )
    return json.dumps(result, ensure_ascii=False)


def get_vector_index_status_tool() -> str:
    """Return persisted vector index status and current collection count."""
    result = get_index_status()
    return json.dumps(result, ensure_ascii=False)

# --- Tool Definitions ---
tools = [
    StructuredTool.from_function(
        func=list_resume_versions_tool,
        name="ListResumeVersions",
        description="Lists all available resume versions stored as YAML. Output example: '- resume'",
        args_schema=EmptyInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=load_complete_resume_tool,
        name="LoadCompleteResume",
        description="Renders the full resume as Markdown. Input: - filename: Resume YAML filename (e.g., 'resume.yaml').",
        args_schema=TextFilenameInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=load_resume_section_tool,
        name="LoadResumeSubmodule",
        description="Loads the Markdown content of a specific resume section. Input: - module_path: Version/section identifier (e.g., 'resume/summary').",
        args_schema=ResumeSectionInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=read_resume_text_tool,
        name="ReadResumeText",
        description="Read editable resume markdown. Input: - target_path: either 'version' for the whole resume text view or 'version/section' for a single section.",
        args_schema=ResumeTextTargetInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=update_resume_section_tool,
        name="WriteResumeSubmodule",
        description="Overwrite a resume section with new Markdown. Input: - module_path: Version/section identifier - new_content: Replacement Markdown preserving headings and bullet lists.",
        args_schema=UpdateResumeSectionInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=replace_resume_text_tool,
        name="ReplaceResumeText",
        description="Replace one exact text snippet in a resume text view. Input: target_path, old_text, new_text. The old_text must match exactly once.",
        args_schema=ReplaceResumeTextInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=insert_resume_text_tool,
        name="InsertResumeText",
        description="Insert text into a resume text view. Input: target_path, new_text, position ('start'|'end'|'before'|'after'), and anchor_text for before/after.",
        args_schema=InsertResumeTextInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=delete_resume_text_tool,
        name="DeleteResumeText",
        description="Delete one exact text snippet from a resume text view. Input: target_path and old_text. The old_text must match exactly once.",
        args_schema=DeleteResumeTextInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=analyze_jd_tool,
        name="AnalyzeJD",
        description="Analyzes job description text to extract key information. Input: - jd_text: Job description text Function: Extracts and structures the following information: - Job Title - Company Name - Key Responsibilities - Required Skills - Required Experience - Educational Requirements - Keywords - Additional Notes Output: Structured analysis in a clear format",
        args_schema=AnalyzeJDInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=create_new_version_tool,
        name="CreateNewVersion",
        description="Creates a new resume version by copying the standard YAML template from templates/resume_template.yaml.",
        args_schema=CreateNewVersionInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=delete_resume_version_tool,
        name="DeleteResumeVersion",
        description="Permanently deletes a resume version. Cannot delete the base 'resume' version. This operation cannot be undone.",
        args_schema=DeleteResumeVersionInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=copy_resume_version_tool,
        name="CopyResumeVersion",
        description="Copies an existing resume version to a new version. Input: source_version (the version to copy from), target_version (the new version name to create).",
        args_schema=CopyResumeVersionInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=update_main_resume_tool,
        name="UpdateResumeIndexFile",
        description="Replace an entire resume YAML definition. Use cautiously—expected content is valid YAML.",
        args_schema=UpdateMainResumeInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=list_modules_in_version_tool,
        name="ListModulesInVersion",
        description="Lists all section identifiers defined in a resume YAML file.",
        args_schema=TextFilenameInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=tailor_section_for_jd_tool,
        name="TailorSectionForJD",
        description="Tailors the content of a specific resume section based on a Job Description analysis using the module's full path.",
        args_schema=TailorSectionForJDInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=read_jd_file_tool,
        name="ReadJDFile",
        description="Reads a job description file from the data/jd directory. Input: - filename: JD filename (e.g., 'job1.txt') Function: Reads and returns the content of the specified job description file Note: Only .txt files are supported",
        args_schema=ReadJDInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=summarize_resumes_to_index_tool,
        name="SummarizeResumesToIndex",
        description="Aggregates resume metadata into resume_summary.yaml for quick scanning.",
        args_schema=EmptyInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=read_resume_summary_tool,
        name="ReadResumeSummary",
        description="Reads the lightweight resume summary YAML and returns it as text.",
        args_schema=EmptyInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=set_section_visibility_tool,
        name="SetSectionVisibility",
        description="Enable or disable a section for rendering. Input: version (no extension), section_id, enabled (true/false).",
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=set_section_order_tool,
        name="SetSectionOrder",
        description="Set preferred section order for a resume version. Input: version (no extension), order (list of section ids).",
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=get_section_style_tool,
        name="GetSectionStyle",
        description="Get current section order and disabled flags for a resume version.",
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=render_resume_to_latex_tool,
        name="RenderResumeToLaTeX",
        description="Render a resume version to LaTeX string. Input: - version name without extension (e.g., 'resume').",
        args_schema=RenderResumeInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=compile_resume_pdf_tool,
        name="CompileResumePDF",
        description="Compile LaTeX content into a PDF using the remote compile service. Input: - tex_content: Full LaTeX document string.",
        args_schema=CompileResumeInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=build_vector_index_tool,
        name="BuildVectorIndex",
        description="Build or refresh semantic vector index for experience/projects entries.",
        args_schema=BuildVectorIndexInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=search_resume_entries_tool,
        name="SearchResumeEntries",
        description="Semantic search for resume entries with filters: entry_type (experience/projects/all), chunk_level (entry/bullet), top_k.",
        args_schema=SearchResumeEntriesInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=get_vector_index_status_tool,
        name="GetVectorIndexStatus",
        description="Get vector index health/status, freshness, and counts.",
        args_schema=EmptyInput,
        return_direct=False,
    ),
]
