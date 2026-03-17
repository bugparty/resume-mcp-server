# MCP Tools Documentation Generator

This directory contains tools and scripts for automatically generating MCP tool documentation.

## 🚀 Quick Start

### Generate All Documentation with One Click

The simplest way is to run the one-click script:

```bash
./generate_all_docs.sh
```

This will automatically generate documentation in three formats:
- `mcp_tools_report.json` - Raw data in JSON format
- `MCP_TOOLS.md` - Documentation in Markdown format
- `MCP_TOOLS.html` - Beautiful documentation in HTML format (recommended for viewing in a browser)

### Manual Step-by-Step Generation

If you need more control, you can execute the steps individually:

#### 1. Export Tool List to JSON

```bash
uv run fastmcp inspect src/myagent/mcp_server.py --format fastmcp -o mcp_tools_report.json
```

#### 2. Generate Markdown Documentation

```bash
python generate_mcp_docs.py mcp_tools_report.json MCP_TOOLS.md
```

#### 3. Generate HTML Documentation

```bash
python generate_mcp_html.py mcp_tools_report.json MCP_TOOLS.html
```

## 📋 Tool Descriptions

### `fastmcp inspect`

Built-in tool provided by FastMCP for inspecting MCP servers and exporting tool information.

**Basic Usage:**
```bash
uv run fastmcp inspect <server_file>
```

**Export JSON:**
```bash
uv run fastmcp inspect <server_file> --format fastmcp -o output.json
```

**Arguments:**
- `--server-spec`: The Python file to inspect
- `--format, -f`: Output format (fastmcp or mcp)
- `--output, -o`: Output file path

### `generate_mcp_docs.py`

Converts the JSON report into Markdown documentation.

**Usage:**
```bash
python generate_mcp_docs.py <json_file> [output_file]
```

**Example:**
```bash
python generate_mcp_docs.py mcp_tools_report.json MCP_TOOLS.md
```

**Features:**
- Automatically categorizes tools (Read-only / Write)
- Displays all parameters and their types, default values
- Clear format and structure

### `generate_mcp_html.py`

Converts the JSON report into beautiful HTML documentation.

**Usage:**
```bash
python generate_mcp_html.py <json_file> [output_file]
```

**Example:**
```bash
python generate_mcp_html.py mcp_tools_report.json MCP_TOOLS.html
```

**Features:**
- Responsive design, adapts to various screens
- Modern gradient color scheme
- Card-style layout, easy to read
- Distinguishes between read-only and write tools
- Displays tool count statistics
- Best viewed in a browser

## 📦 Custom Usage

### Generate Documentation for Other MCP Servers

If you have other MCP servers, simply modify the server path in the `generate_all_docs.sh` script:

```bash
./generate_all_docs.sh path/to/your/mcp_server.py
```

### Custom Output Filenames

```bash
# Generate to custom location
python generate_mcp_docs.py input.json output.md
python generate_mcp_html.py input.json output.html
```

## 📝 Generated Documentation Content

The generated documentation includes the following information:

### Summary
- Total Tool Count
- Read-only Tool Count
- Write Tool Count
- Prompt Count
- Template Count

### Tool Details (Per Tool)
- Tool Name
- Description
- Parameter List
  - Parameter Name
  - Parameter Type
  - Required?
  - Default Value

### Prompts
- Prompt Name
- Prompt Description

### Templates
- Template Name
- URI Template
- Template Description

## 🎯 Use Cases

1. **Team Collaboration**: Share generated documentation with team members to help them understand available MCP tools
2. **API Documentation**: As the official API documentation for the MCP service
3. **Version Control**: Include documentation in version control to track API changes across versions
4. **Automation**: Integrate into CI/CD pipelines to automatically update documentation on every code change

## 📄 File Descriptions

- `generate_all_docs.sh` - Shell script to generate all documentation with one click
- `generate_mcp_docs.py` - Python script to generate Markdown documentation
- `generate_mcp_html.py` - Python script to generate HTML documentation
- `mcp_tools_report.json` - Tool report in JSON format (automatically created during generation)
- `MCP_TOOLS.md` - Documentation in Markdown format (automatically created during generation)
- `MCP_TOOLS.html` - Documentation in HTML format (automatically created during generation)

## 🤝 Contribution

If you have suggestions for improvement or find issues, welcome to submit Issues or Pull Requests.

## 📄 License

Consistent with the main project.
