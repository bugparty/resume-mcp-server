# Project Name: Modular Intelligent Resume Generation System

## Project Goal
Build an automated system that intelligently selects and modifies modular LaTeX resume components based on different job descriptions (JD), and combines them into a complete customized resume document.

## Functional Overview

- Supports modular resume structure (each module is a `.tex` file)
- Supports multiple resume versions (e.g., resume_2yoe_c++, resume_frontend)
- Automatically extracts keywords and analyzes job descriptions (JD)
- Intelligently customizes resume content to adapt to target positions
- Supports creating new resume versions
- Supports condensing and re-extracting resume modules
- Supports full resume content preview and editing

## Directory Structure Convention

```
data/BowenResume/
├── resume/                    # General version modules
│   ├── summary.tex
│   ├── projects.tex
│   ├── skills.tex
│   └── ...
├── resume_2yoe_c++/           # Specific direction modules
│   ├── summary.tex
│   ├── projects.tex
│   ├── skills.tex
│   └── ...
└── cv/                        # More academic modules
```

## Data Directory Explanation
The data directory contains my resume. `resume_xxx.tex` are different versions I created for different positions. When `resume_xxx.tex` is opened, it contains `\input` commands for other tex files, used to include different versions of summary, education, skills, experience, etc.

## Agent Architecture

Uses LangChain + custom tool functions to form a ReAct Agent architecture.

### Implemented Tools:
- `list_resume_versions`: List all available resume versions
- `load_resume_modules`: Load and preview content of a specific resume version
- `load_resume_section`: Load a single module content
- `update_resume_section`: Update specific module content (with automatic backup)
- `analyze_jd`: Analyze job description, extract key information
- `create_new_version`: Create a new resume version
- `list_modules_in_version`: List all modules in a specific version
- `tailor_section_for_jd`: Customize specific module content based on JD
- `update_main_resume`: Update the main resume file content
- `read_jd_file`: Read job description file
- `load_complete_resume`: Load complete resume content
- `summarize_resumes_to_index`: Extract resume metadata to generate a lightweight index
- `read_resume_summary`: Read the lightweight resume index file

## Example Call
User Input:
```
Please load matching modules from resume_2yoe_c++ based on the JD below, and generate a customized resume.
JD: We are looking for candidates with C++ project experience and experience in open source system development.
```

Agent Call Flow:
1. Use `analyze_jd` to analyze JD -> extract keywords and requirements
2. Use `list_resume_versions` to view available versions
3. Use `load_resume_modules` to preview module content
4. Use `tailor_section_for_jd` to customize each module content
5. Use `update_resume_section` to update module content
6. Use `update_main_resume` to update the main resume file

## Technical Implementation Details

- Use Cloudflare AI Gateway as LLM debugging middleware and to accelerate DeepSeek access
- Use Jinja2 for template rendering
- Implemented automatic backup mechanism to ensure data safety
- Supports intelligent customization of modular content
- Use YAML format for resume content aggregation and management

## Future Expansions

- Web Interface (e.g., Streamlit or Gradio)
- Add Cover Letter generator
- Module recommendation sorting optimization
- Resume scoring (match analysis)
- Support more resume formats (e.g., Markdown, HTML)
- Add resume version management function
- Implement semantic search for resume content

## Dependency Management

This project uses `uv` for package management. Please use `uv pip install` to install dependencies.

## New Environment Variables (Async PDF Compilation)

- `CELERY_BROKER_URL`: Celery broker address (default `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND`: Celery result backend (default `redis://localhost:6379/1`)
- `CELERY_TASK_TIME_LIMIT`: Compilation task hard timeout (seconds, default 120)
- `CELERY_TASK_SOFT_TIME_LIMIT`: Compilation task soft timeout (seconds, default 90)
- `RESUME_PDF_JOB_PREFIX`: S3 job directory prefix (default `resume-jobs/`)

S3 related configurations still use existing variables:
- `RESUME_S3_BUCKET_NAME` / `RESUME_S3_BUCKET`
- `RESUME_S3_ENDPOINT_URL`
- `RESUME_S3_REGION`
- `RESUME_S3_ACCESS_KEY_ID` / `RESUME_S3_SECRET_ACCESS_KEY`
- `RESUME_S3_PUBLIC_BASE_URL`
- `RESUME_S3_KEY_PREFIX`
