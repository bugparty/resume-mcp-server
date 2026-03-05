# Resume MCP Agent

## 🤖 What is Resume MCP Agent?

Resume MCP Agent is an intelligent resume assistant based on MCP (Model Context Protocol) that allows you to directly manage and optimize your resume within AI clients like Claude Desktop and ChatGPT.

### 🎯 What can it do for you?

**📝 Smart Resume Management**
- Automatically read and analyze your resume content
- Support multiple resume versions for easy switching and comparison
- Real-time preview with instant results

**🎯 Precise Job Matching**
- Upload job descriptions and automatically analyze key requirements
- Intelligent recommendations for resume optimization
- One-click generation of tailored resumes for specific positions

**📄 Professional PDF Output**
- Automatically generate beautiful PDF resumes
- Support custom templates and formats
- Ensure proper formatting suitable for direct submission

**🔄 Seamless AI Integration**
- Direct operation within Claude Desktop
- Support for ChatGPT Developer Mode
- Complete all operations through natural language commands

### 💡 Typical Use Cases

1. **Job Preparation**: Create customized resume versions for different companies
2. **Resume Optimization**: Adjust content and keywords based on job requirements
3. **Format Conversion**: Convert from Word/PDF to structured data for easy management
4. **Batch Processing**: Quickly generate multiple resume versions

## 🚀 Quick Start

### Option 1: Docker Deployment (Recommended)

For the easiest setup, use Docker to get started in minutes:

```bash
# Build the image
docker build -t resume-mcp:latest .

# Run with automatic Cloudflare tunnel (recommended with data persistence)
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/templates:/app/templates" \
  --env-file ./.env \
  resume-mcp:latest
```

The container will automatically create a public URL for ChatGPT integration. See [Docker Guide](./DOCKER.md) for detailed instructions.

### Option 2: Local Setup

1. **Clone and setup environment**
   ```bash
   git clone <repository-url>
   cd resume_mcp
   ./setupenv.sh
   ```

2. **Configure environment variables**
   ```bash
   cp sample.env .env
   # Edit .env with your API keys
   ```

3. **Configure external compile service** (for PDF generation)
   - Set `LATEX_COMPILE_API_URL` in `.env`
   - Default service: `https://latex-compile.k.0x1f0c.dev`
   - See API details in [LaTeX Compile API](./docs/latex_compile_api.md)

4. **Start the MCP server**

   **For Claude Desktop (STDIO mode):**
   ```bash
   uv run python scripts/start_mcp_server.py --transport stdio
   ```

   **For HTTP mode (testing/ChatGPT):**
   ```bash
   uv run python scripts/start_mcp_server.py --transport http --port 8000
   ```

5. **Expose via Cloudflare Tunnel (optional, for ChatGPT)**
   
   If using HTTP mode and want to access from ChatGPT:
   
   ```bash
   # In another terminal, start Cloudflare tunnel
   cloudflared tunnel --url http://localhost:8000
   ```
   
   Cloudflare will return a URL like `https://xxx.trycloudflare.com`
   
   **ChatGPT client configuration:**
   - Server URL: use the HTTPS URL from Cloudflare
   - Authentication: None
   - Protocol: HTTP/HTTPS

## 📚 Documentation

- **[MCP Setup Guide](./MCP_SETUP.md)** - Detailed MCP server configuration and client connection
- **[User Manual](./MCP_USER_MANUAL.md)** - Tool usage guide and typical workflows
- **[Docker Guide](./DOCKER.md)** - Docker deployment and cloud access configuration
- **[Resume Version Management](./docs/resume_version_management.md)** - Resume version management

## 🛠️ Development

### Testing
```bash
# Run all tests
uv run python scripts/run_all_tests.py

# Run specific test
uv run pytest tests/test_resume_rendering.py
```

### CLI Tools
```bash
# Generate LaTeX
uv run python scripts/render_resume_cli.py resume

# Generate PDF
uv run python scripts/render_resume_cli.py resume --tex build/resume.tex --pdf build/resume.pdf --compile
```

## 📋 Requirements

- Python 3.12+
- UV package manager
- External LaTeX compile service (`LATEX_COMPILE_API_URL`)

## 🚀 Ready to Start

Whether you're a job seeker, HR professional, or developer, you can get started quickly:
- **Regular users**: Use Docker for one-click deployment in 5 minutes
- **Developers**: Set up local environment for full control and customization

For detailed setup instructions and troubleshooting, see the [MCP Setup Guide](./MCP_SETUP.md).