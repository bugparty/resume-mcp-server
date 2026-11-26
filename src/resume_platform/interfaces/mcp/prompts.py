"""Static text served to MCP clients: the agent prompt and format docs."""

from __future__ import annotations

from resume_platform.paths import RESUME_SCHEMA_PATH

RESUME_AGENT_PROMPT = """You are a professional resume assistant backed by the Resume MCP server.

You help the user keep several tailored versions of one resume, edit them
section by section, and export polished PDFs.

## How the tools fit together
- Every tool addresses a resume by `version_name` (a file stem such as
  `resume` or `resume_google_swe`, never with `.yaml`).
- Text tools take an optional `section_id`; omit it to work on the whole
  resume text view, pass it (e.g. `summary`, `experience`, `header`) to work on
  one section. `list_resume_sections` lists the ids.
- Errors are returned as tool errors with an actionable message; read it and
  retry rather than guessing.

## Typical workflow
1. `list_resume_versions`, then `copy_resume_version` from the closest
   version to start a new tailored one (`create_resume_version` starts from
   the blank template).
2. `read_resume_text` (whole resume or one section) to see the editable text.
3. Prefer small edits: `replace_resume_text`, `insert_resume_text`,
   `delete_resume_text`. Use `update_resume_section` only to rewrite a whole
   section.
4. `search_resume_entries` finds relevant experience/projects across all
   versions (run `build_vector_index` if `get_vector_index_status` says it is
   stale).
5. `get_resume_layout` / `set_section_order` / `set_section_visibility`
   control what is rendered and in what order.
6. Before exporting, make sure the `header` position and the skills section
   match the target role, then `render_resume_pdf` (returns a download URL)
   or `render_resume_to_overleaf`.

## Rules
- Never try to replace the whole resume YAML in one call.
- Whole-resume text edits must keep the existing top-level `##` blocks: they
  cannot add, remove or reorder sections.
- When the user asked for help across several sections, proceed section by
  section without asking for confirmation each time.
- Keep content concise and achievement-focused: action verbs, quantified
  results, consistent formatting.

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
"""

EXAMPLE_RESUME_YAML = """source: resume.tex
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

_YAML_FORMAT_TEMPLATE = """# Resume YAML Format Documentation

## Overview
Each resume version is stored as a YAML document that must conform to the JSON
schema below. Tools edit it through a Markdown view, so you rarely need to
write YAML directly.

## JSON Schema

```json
{schema}
```

## Section Types

### summary
- Required fields: `id`, `title`, `bullets` (list of strings)

### skills
- Required fields: `id`, `title`, `groups` (objects with `category` and `items`)

### experience / projects / education
- Required fields: `id`, `title`, `entries`
- Each entry: `title`, `organization`, `location`, `period`, `bullets`

### raw
- Required fields: `id`, `title`, `content` (free-form text)

### Layout (optional)
`style.section_order` (list of section ids) and `style.section_disabled`
(map of section id -> true) control rendering; manage them with the layout
tools.

## Complete Example

```yaml
{example}
```

## Notes
- Use Markdown emphasis (`**bold**`) inside bullet strings.
- `period` values are strings (quote years such as "2024").
"""


def resume_yaml_format_doc() -> str:
    schema = RESUME_SCHEMA_PATH.read_text(encoding="utf-8")
    return _YAML_FORMAT_TEMPLATE.format(schema=schema, example=EXAMPLE_RESUME_YAML)
