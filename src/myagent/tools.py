from pathlib import Path
import shutil
import tempfile
import json

from langchain_core.messages import HumanMessage
from .llm_config import get_thinking_llm
from .resume_loader import (
    find_resume_versions,
    load_resume_section,
    update_resume_section,
    create_new_version,
    list_modules_in_version,
    update_main_resume,
    tailor_section_for_jd,
    load_complete_resume,
    summarize_resumes_to_index,
    read_resume_summary,
)
from .resume_renderer import render_resume, compile_tex
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from .settings import get_settings
from .filesystem import get_jd_fs, get_output_fs


# --- Pydantic Models for Tool Input ---
class EmptyInput(BaseModel):
    """Empty input model for tools that don't require parameters."""
    pass

class TextFilenameInput(BaseModel):
    filename: str = Field(..., description="The resume filename, e.g., 'resume.yaml'")

class ResumeSectionInput(BaseModel):
    module_path: str = Field(..., description="Resume section path using 'version/section', e.g., 'resume/summary'")

class UpdateResumeSectionInput(BaseModel):
    module_path: str = Field(..., description="Resume section path using 'version/section', e.g., 'resume/summary'")
    new_content: str = Field(..., description="Updated Markdown content for the section")

class AnalyzeJDInput(BaseModel):
    jd_text: str = Field(..., description="The full text of the Job Description to analyze")

class CreateNewVersionInput(BaseModel):
    new_version_name: str = Field(..., description="The name for the new resume version, e.g., 'resume_for_google'")

class DeleteResumeVersionInput(BaseModel):
    version_name: str = Field(..., description="The name of the resume version to delete, e.g., 'resume_for_google'")

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

# --- Tool Implementation Functions ---
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

def update_resume_section_tool(module_path: str, new_content: str) -> str:
    """
    Updates the Markdown content of a resume section.
    Input:
    - module_path: Version/section identifier
    - new_content: Markdown to replace the section body while preserving headings/bullets
    """
    return update_resume_section(module_path, new_content)

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
    return create_new_version(new_version_name)

def delete_resume_version_tool(version_name: str) -> str:
    """
    Delete a resume version permanently.
    Input:
    - version_name: The name of the resume version to delete (without .yaml extension)
    Note: This operation cannot be undone. Ensure you have backups if needed.
    """
    from .filesystem import get_resume_fs
    
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
        return f"[Success] Resume version '{version_name}' has been deleted successfully."
    except Exception as e:
        return f"[Error] Failed to delete resume version '{version_name}': {str(e)}"

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
    return update_main_resume(file_name, file_content)

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


def render_resume_to_latex_tool(version: str) -> RenderResumeOutput:
    """Render a resume version to LaTeX string."""
    latex = render_resume(version)
    return RenderResumeOutput(latex=latex)


def compile_resume_pdf_tool(tex_content: str, version_name: str = "resume") -> CompileResumeOutput:
    """Compile LaTeX content into a PDF using xelatex."""
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

        compile_tex(tex_path)
        pdf_path = tex_path.with_suffix(".pdf")
        
        # Generate filename with version name and timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{version_name}_{timestamp}.pdf"
        
        # Use output filesystem to save the PDF
        output_fs = get_output_fs()
        with open(pdf_path, 'rb') as src_file:
            output_fs.writebytes(output_filename, src_file.read())

    return CompileResumeOutput(pdf_path="data://resumes/output/" + output_filename)

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
        func=update_resume_section_tool,
        name="WriteResumeSubmodule",
        description="Overwrite a resume section with new Markdown. Input: - module_path: Version/section identifier - new_content: Replacement Markdown preserving headings and bullet lists.",
        args_schema=UpdateResumeSectionInput,
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
        func=render_resume_to_latex_tool,
        name="RenderResumeToLaTeX",
        description="Render a resume version to LaTeX string. Input: - version name without extension (e.g., 'resume').",
        args_schema=RenderResumeInput,
        return_direct=False,
    ),
    StructuredTool.from_function(
        func=compile_resume_pdf_tool,
        name="CompileResumePDF",
        description="Compile LaTeX content into a PDF using xelatex. Input: - tex_content: Full LaTeX document string.",
        args_schema=CompileResumeInput,
        return_direct=False,
    ),
]
