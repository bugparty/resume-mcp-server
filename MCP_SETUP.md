# FastMCP Resume Agent Server - Quick Start

## 🏃‍♂️ Quick Start

### Option 1: Start the HTTP server directly (recommended)

```bash
cd resume_mcp
uv run python src/myagent/mcp_server.py
```

The server will start at http://localhost:8000 and expose an HTTP API.

### Option 2: Use the startup script (STDIO mode) for Claude

```bash
cd resume_mcp
uv run python scripts/start_mcp_server.py
```

### 🌐 Expose via Cloudflare Tunnel (for ChatGPT)

If you want external clients like ChatGPT to access the server, use Cloudflare Tunnel:

1. **Start the MCP server:**
   ```bash
   uv run python src/myagent/mcp_server.py
   ```

2. **Start the Cloudflare tunnel:**
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

3. **Get a public URL:**
   Cloudflare will return a URL like `https://xxx.trycloudflare.com`

4. **ChatGPT client configuration:**
   - Server URL: use the HTTPS URL from Cloudflare
   - Authentication: None
   - Protocol: HTTP/HTTPS

### 🖥️ Use in Claude Desktop

Add the following to Claude Desktop's MCP configuration:

```json
{
  "mcpServers": {
    "resume-agent": {
      "command": "uv",
      "args": ["run", "python", "scripts/start_mcp_server.py"],
      "cwd": "/path/to/resume_mcp"
    }
  }
}
```

## 🧪 Test the Server

### 1. Test server startup
```bash
cd resume_mcp
uv run python scripts/test_mcp_server.py
```

### 2. Test HTTP endpoints

When running in HTTP mode, you can test with:

```bash
# Check server health
curl http://localhost:8000/health

# List available tools
curl http://localhost:8000/tools
```

### 3. Test via Cloudflare tunnel

```bash
# Use the Cloudflare-provided URL
curl https://xxx.trycloudflare.com/health
```

## 💡 Usage Examples

After starting, you can run these commands in Claude Desktop:

```
list_resume_versions()  # list all resume versions
load_complete_resume("resume.yaml")  # load full resume
analyze_jd("Job description text here...")  # analyze a job description
```

Use the HTTP interface in ChatGPT:

```json
{
  "tool": "list_resume_versions",
  "args": {}
}
```

## 🔧 Technical Highlights

- **Zero changes**: fully reuses functionality from tools.py
- **Dual modes**: supports STDIO and HTTP
- **Cloud access**: expose to external clients via Cloudflare Tunnel
- **Type-safe**: retains original Pydantic models
- **Standard protocol**: fully compatible with MCP

## 🛠️ Configuration

### Environment variables

Ensure required environment variables are configured (copy `sample.env` to `.env`):

```bash
cp sample.env .env
# Edit .env and set required API keys and paths
```

### Cloudflare Tunnel configuration

For a persistent tunnel, configure Cloudflare Tunnel:

```bash
# Create a tunnel
cloudflared tunnel create myagent-mcp

# Route DNS
cloudflared tunnel route dns myagent-mcp myagent-mcp.yourdomain.com

# Run the tunnel
cloudflared tunnel run myagent-mcp
```

## 🐛 Troubleshooting

### Common issues

1. **Import errors**: ensure commands are run from the project root
2. **Port in use**: check that port 8000 is free
3. **Environment variables**: confirm `.env` is configured correctly
4. **Missing dependencies**: run `uv sync` to install all deps

### Logging and debugging

```bash
# Show verbose logs at startup
python src/myagent/mcp_server.py --verbose
```

See the detailed docs: `docs/mcp_server.md`

## 🚀 Setup Complete

Your Resume Agent is now exposed as an MCP server via FastMCP! It supports local runs and external access via Cloudflare Tunnel.

### 📁 New Files
- `src/myagent/mcp_server.py` - MCP server entrypoint
- `scripts/start_mcp_server.py` - startup script
- `scripts/test_mcp_server.py` - test script
- `docs/mcp_server.md` - detailed documentation

### 🛠️ Available Tools (14)

#### Resume Version Management
- `list_resume_versions` - list all resume versions
- `load_complete_resume` - load full resume
- `load_resume_section` - load a specific section
- `update_resume_section` - update a section
- `create_new_version` - create a new version
- `list_modules_in_version` - list sections in a version
- `update_main_resume` - update the whole resume file

#### Job Description Analysis
- `analyze_jd` - analyze a job description
- `read_jd_file` - read a JD file
- `tailor_section_for_jd` - tailor a resume section for the JD

#### Resume Summary and Index
- `summarize_resumes_to_index` - generate resume summary index
- `read_resume_summary` - read resume summary

#### Resume Rendering
- `render_resume_to_latex` - render to LaTeX
- `compile_resume_pdf` - compile to PDF
