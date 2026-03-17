# Resume Agent Tools Documentation

## Server Information

- **Name**: Resume Agent Tools
- **MCP Version**: 2

## Summary

- **Total Tools**: 19
- **Total Prompts**: 1
- **Total Resources**: 0
- **Total Templates**: 1

## Tools

### Read-Only Tools

**9 tools**

#### `list_data_directory`

**Description**: List contents of the data directory or a subdirectory within it.

Args:
    path: Relative path within the data directory (empty string for root)

Returns:
    JSON string containing directory listing with file/folder info

**Parameters**:

- `path` (string) *(optional)*, default: ``


---

#### `list_resume_versions`

**Description**: Lists all available resume versions stored as YAML files.

Returns:
    JSON string containing the version names and total count.

**Parameters**: None

---

#### `load_complete_resume`

**Description**: Renders the full resume as Markdown.

Args:
    version_name: Resume version name WITHOUT .yaml extension (e.g., 'resume')

**Parameters**:

- `version_name` (string) *(required)*


---

#### `get_resume_section`

**Description**: Load a specific section from a resume file.

Args:
    version_name: Resume file name WITHOUT .yaml extension (e.g., 'resume')
    section_id: Section identifier to load (must be one of: header, summary, 
               skills, experience, projects, education, custom)

Returns:
    Markdown content of the requested section
    
Example:
    get_resume_section(version_name="resume", section_id="summary")

**Parameters**:

- `version_name` (string) *(required)*
- `section_id` (string) *(required)*


---

#### `get_resume_layout`

**Description**: Get current section order and disabled flags for a resume version.

**Parameters**:

- `version_name` (string) *(required)*


---

#### `list_resume_sections`

**Description**: List all section identifiers available in a resume file.

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

**Parameters**:

- `version_name` (string) *(required)*


---

#### `read_resume_summary`

**Description**: Reads the lightweight resume summary YAML and returns it as text.

**Parameters**: None

---

#### `get_resume_yaml_format`

**Description**: Returns comprehensive documentation about the Resume YAML format including schema and examples.

This function provides:
1. The JSON schema that validates resume YAML files
2. A complete example of a properly formatted resume YAML
3. Detailed explanations of each section type

Use this before calling update_main_resume to understand the required YAML structure.

**Parameters**: None

---

#### `get_resume_pdf_job_status`

**Description**: Query the status of an async resume PDF job by Celery task id.

**Parameters**:

- `task_id` (string) *(required)*


---

### Write Tools

**10 tools**

#### `update_resume_section`

**Description**: Update a specific section in a resume file with new Markdown content.

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

**Parameters**:

- `version_name` (string) *(required)*
- `section_id` (string) *(required)*
- `new_content` (string) *(required)*

---

#### `set_section_visibility`

**Description**: Enable or disable rendering of a specific section in a resume version.

Args:
    version: Resume version name (without .yaml)
    section_id: Section id to toggle (e.g., 'summary', 'experience')
    enabled: True to show, False to hide

**Parameters**:

- `version_name` (string) *(required)*
- `section_id` (string) *(required)*
- `enabled` (boolean) *(optional)*, default: `True`

---

#### `set_section_order`

**Description**: Set the rendering order of sections for a resume version.

Args:
    version: Resume version name (without .yaml)
    order: List of section ids in desired order; unknown ids are skipped and remaining sections are appended automatically.

**Parameters**:

- `version_name` (string) *(required)*
- `order` (array) *(required)*

---

#### `create_new_version`

**Description**: Creates a new resume version by copying the default YAML template.

Args:
    new_version_name: The name for the new resume version (e.g., 'resume_for_google')

**Parameters**:

- `new_version_name` (string) *(required)*

---

#### `delete_resume_version`

**Description**: Permanently deletes a resume version.

Args:
    version_name: The name of the resume version to delete (without .yaml extension)

Note:
    - Cannot delete the base 'resume' version
    - This operation cannot be undone
    - Ensure you have backups if needed

**Parameters**:

- `version_name` (string) *(required)*

---

#### `copy_resume_version`

**Description**: Copies an existing resume version to a new version.

Args:
    source_version: The name of the source resume version to copy from (without .yaml extension)
    target_version: The name of the target resume version to copy to (without .yaml extension)

Note:
    - The source version must exist
    - The target version must not already exist

**Parameters**:

- `source_version` (string) *(required)*
- `target_version` (string) *(required)*

---

#### `summarize_resumes_to_index`

**Description**: Aggregates resume metadata into resume_summary.yaml for quick scanning.

Returns:
    Dictionary with yaml_path and message about the indexing process

**Parameters**: None

---

#### `render_resume_pdf`

**Description**: Render a resume version directly to PDF file. **This is a WRITE tool** because it
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

**Parameters**:

- `version_name` (string) *(required)*

---

#### `submit_resume_pdf_job`

**Description**: Submit an async resume render+compile job.

This tool renders LaTeX, uploads the LaTeX and assets bundle to S3, and
enqueues a Celery job for PDF compilation. It returns job/task identifiers.

**Parameters**:

- `version_name` (string) *(required)*

---

#### `render_resume_to_overleaf`

**Description**: Render a resume version to a LaTeX project suitable for Overleaf import.

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

**Parameters**:

- `version_name` (string) *(required)*

---

## Prompts

### `resume_agent_prompt`

**Description**: System prompt for the Resume Agent MCP Server.

This prompt guides AI assistants on how to use this server effectively
for resume management and job application optimization.

---

## Templates

### `read_data_file`

**URI Template**: `data://{path}`

**Description**: Read files from the data directory.

Args:
    path: Relative path within the data directory

Returns:
    File content as string for text files, bytes for binary files

---

---

*Generated by fastmcp inspect*