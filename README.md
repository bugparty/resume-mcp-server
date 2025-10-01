# Setting Up UV and Environment

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd resume_mcp
   ```

2. **Create and Activate Virtual Environment**
   ```bash
   uv venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows
   .venv\Scripts\activate
   ```

3. **Install Dependencies (pyproject.toml)**
   ```bash
   uv sync
   ```

4. **Install Dependencies (requirements.txt) you either use uv sync or pip install but not both**
   ```bash
   uv pip install -r requirement.txt
   ```

5. **Start the MCP Server**
   ```bash
   # HTTP transport (easy to test locally)
   uv run python scripts/start_mcp_server.py --transport http --port 8000

   # Or stdio transport (for MCP clients)
   uv run python scripts/start_mcp_server.py --transport stdio
   ```

6. **CLI Resume Rendering**
   ```bash
   # Print LaTeX to stdout
   uv run python scripts/render_resume_cli.py resume

   # Save LaTeX and compile to PDF
   uv run python scripts/render_resume_cli.py resume \
       --tex build/resume.tex \
       --pdf build/resume.pdf \
       --compile
   ```

7. **Run Test Suite (Schema, pytest, PDF)**
   ```bash
   uv run python scripts/run_all_tests.py
   ```

8. **Load Environment Variables**
   Ensure `.env` contains entries such as:
   ```env
   GOOGLE_API_KEY=...
   DEEPSEEK_API_KEY=...
   RESUME_DATA_DIR=/data/resumes
   RESUME_SUMMARY_PATH=/src/myagent/resume_summary.yaml
   RESUME_JD_DIR=/data/jd
   ```

9. **Optional: Manual PDF Compilation**
   ```bash
   xelatex build/resume.tex
   ```

## MCP Usage
- See `docs/mcp_server.md` and `MCP_SETUP.md` for connecting an MCP client and available tools.

## Notes
- Replace `<repository-url>` with the actual URL of the repository
- UV is significantly faster than traditional pip for package installation
- The project uses Python 3.12 as specified in pyproject.toml
- DEEPSEEK API TOKEN is required, only  USD needed
- Google API Key is free and available from Google AI Studio
- For more information about UV, visit [UV documentation](https://github.com/astral-sh/uv)
- CLI tools: render & compile via `scripts/render_resume_cli.py`
- LangChain tools: `RenderResumeToLaTeX` and `CompileResumePDF`
- Run tests (schema, pytest, PDF): `uv run python scripts/run_all_tests.py`
- PDF generation requires `xelatex` and the Awesome-CV assets (under `templates/`)

## Tools

### SummarizeResumesToIndex
- LangChain tool name: `SummarizeResumesToIndex`
- Python directly: `from myagent.tools import summarize_resumes_to_index_tool`
- Regenerates the lightweight `resume_summary.yaml` snapshot.

### ReadResumeSummary
- LangChain tool name: `ReadResumeSummary`
- Python directly: `from myagent.tools import read_resume_summary_tool`
- Returns the lightweight summary content for quick inspection.

### RenderResumeToLaTeX
- LangChain tool name: `RenderResumeToLaTeX`
- Python directly: `from myagent.tools import render_resume_to_latex_tool`
- Returns raw LaTeX for a given resume version.

### CompileResumePDF
- LangChain tool name: `CompileResumePDF`
- Python directly: `from myagent.tools import compile_resume_pdf_tool`
- Requires `xelatex` and Awesome-CV assets (`templates`). Returns a PDF path.

### CLI Utility
- `uv run python scripts/render_resume_cli.py resume` (LaTeX output)
- `uv run python scripts/render_resume_cli.py resume --tex build/resume.tex --pdf build/resume.pdf --compile`

## Testing

- One-stop suite (schema, pytest, PDF):
  ```bash
  uv run python scripts/run_all_tests.py
  ```
- PDF rendering unit test:
  ```bash
  uv run pytest tests/test_resume_rendering.py
  ```
