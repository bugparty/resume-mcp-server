# Resume Agent MCP Server

This MCP (Model Context Protocol) server exposes all resume management tools from the Resume Agent project, allowing them to be used by MCP clients like Claude Desktop, VS Code extensions, and other compatible applications.

## Available Tools

### Resume Version Management
- **list_resume_versions**: Lists all available resume versions
- **load_complete_resume**: Renders full resume as Markdown
- **load_resume_section**: Loads specific resume section content
- **update_resume_section**: Updates resume section with new content
- **create_new_version**: Creates new resume version from template
- **list_modules_in_version**: Lists all sections in a resume version
- **update_main_resume**: Updates entire resume YAML file

### Job Description Analysis
- **analyze_jd**: Analyzes job description text to extract key information
- **read_jd_file**: Reads job description files from data/jd directory
- **tailor_section_for_jd**: Customizes resume sections based on JD analysis

### Resume Summary and Indexing
- **summarize_resumes_to_index**: Creates lightweight resume summary
- **read_resume_summary**: Reads the resume summary YAML

### Resume Rendering
- **render_resume_to_latex**: Converts resume to LaTeX format
- **compile_resume_pdf**: Compiles LaTeX to PDF using xelatex

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Setup environment variables (copy `sample.env` to `.env`):
   ```bash
   cp sample.env .env
   # Edit .env with your API keys and paths
   ```

## Usage

### Starting the Server

```bash
# From project root
python scripts/start_mcp_server.py
```

Or directly:
```bash
# From project root
python -m myagent.mcp_server
```

### Using with Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "resume-agent": {
      "command": "python",
      "args": ["/path/to/myagent/scripts/start_mcp_server.py"]
    }
  }
}
```

### Using with VS Code

Install an MCP extension and configure it to connect to the server.

## Example Workflows

### 1. Analyze Job Description and Tailor Resume
```
1. read_jd_file("tesla_job.txt")
2. analyze_jd(jd_content)
3. load_resume_section("resume/summary")
4. tailor_section_for_jd("resume/summary", current_content, jd_analysis)
5. update_resume_section("resume/summary", tailored_content)
```

### 2. Create Customized Resume Version
```
1. create_new_version("resume_for_tesla")
2. list_modules_in_version("resume_for_tesla.yaml")
3. load_resume_section("resume_for_tesla/experience")
4. update_resume_section("resume_for_tesla/experience", customized_content)
5. render_resume_to_latex("resume_for_tesla")
6. compile_resume_pdf(latex_content)
```

### 3. Resume Management and Overview
```
1. list_resume_versions()
2. summarize_resumes_to_index()
3. read_resume_summary()
```

## Architecture

The MCP server acts as a bridge between the existing LangChain-based tools in `tools.py` and the MCP protocol. It:

1. Wraps each tool function with MCP decorators
2. Preserves the original Pydantic schemas for type safety
3. Maintains all existing functionality without modification
4. Provides standardized tool descriptions for MCP clients

## Development

To add new tools:

1. Add the tool function to `src/myagent/tools.py`
2. Add the corresponding MCP wrapper in `src/myagent/mcp_server.py`
3. Update this documentation

## Troubleshooting

- Ensure all environment variables are set correctly
- Check that the resume data directory contains valid YAML files
- Verify LaTeX installation for PDF compilation features
- Check logs for specific error messages