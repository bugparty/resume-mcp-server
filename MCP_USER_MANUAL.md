## MCP Server User Guide (Resume Agent Tools)

This manual is for end users. It explains what the resume agent's MCP server can do, how to get started quickly, how the documentation is organized, and how the code modules are structured.

For instructions on installing/connecting an MCP client, see [MCP Setup Guide](./MCP_SETUP.md).

### Introduction
- **Positioning**: Uses MCP (Model Context Protocol) to unify resume management, JD (job description) analysis, and PDF rendering into a set of remotely callable tools, making integration easy for desktop clients (e.g., Claude Desktop, ChatGPT developer mode) or automation workflows.
- **Data scope**: Controlled access to the project root's `data/` directory (with path normalization and prefix validation).
- **Logs**: Runtime logs and tool invocation records are written to `logs/mcp_server.log`.
 
### Client Integration
- Desktop MCP clients/plugins can be configured to connect to this service per their documentation (see `mcp_setup.md` above).

### Features

Resume structure
This section outlines the modules that make up a resume.

- **What you can do**
  - Upload or provide your PDF resume; the system will automatically convert it into editable resume content (you may need to confirm and fine-tune the conversion).
  - Browse and select resume versions.
  - Ask the assistant to review all of your resume versions and generate a new one that better matches a given JD (focuses on the JD's requirements and keywords).
  - Given a JD, ask the assistant to highlight relevant keywords within a selected resume version, then render a preview/export.
  - Edit common sections: summary, skills, work experience, projects, education.
  - Export to PDF for submission or sharing.
  - You can also paste JD text directly into the conversation. The assistant will automatically select relevant experiences from your history, assemble a new version, and export it to PDF (exported files are typically located under `data/resumes/output/`).

- **Typical workflow**
  1. Choose a resume version (or let the assistant pick one) / create a new resume version.
  2. Tell the assistant which sections/content to edit and how to edit them, then follow the prompts.
  3. Preview the full resume (optional).
  4. Export to PDF (optional).

- **Common scenarios**
  - Quickly refine your summary/skills to make the resume more aligned with the target role.
  - Create different versions for different companies and maintain distinct emphases.
  - Export the latest PDF before submitting.

- **Notes**
  - Changes are saved automatically; exports will use the current content.
  - If the preview does not update, refresh the view or try again later.
  - You do not need to understand the underlying format or rendering details; just follow the UI prompts.
  - PDF conversion and rendering may take a few seconds; content converted from PDF may not be perfect, so we recommend a quick check of key information before exporting.
 
- **Resume storage format**
  - Resume content is stored in the project's `data/resumes` directory (files ending in `.yaml`). Manual editing is usually unnecessary; if you must edit manually, proceed with caution.
  - After exporting to PDF, you can usually find the file under `data/resumes/output/`.
