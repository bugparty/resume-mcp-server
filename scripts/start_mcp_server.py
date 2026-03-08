#!/usr/bin/env python3
"""
Start script for the Resume Agent MCP Server

This script sets up the Python path and starts the MCP server,
making all resume management tools available via the MCP protocol.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Start Resume Agent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                        help="Transport type (default: stdio)")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port for HTTP transport (default: 8000)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload in HTTP mode (development only)",
    )
    
    args = parser.parse_args()

    if args.reload and args.transport != "http":
        parser.error("--reload only supports --transport http")
    
    print("🚀 Starting Resume Agent MCP Server...")
    print("📋 Available tools:")
    print("  - Resume Version Management (list, load, create, update)")
    print("  - Job Description Analysis")
    print("  - Resume Section Tailoring")
    print("  - Direct PDF Generation (render_resume_pdf)")
    print("  - Resume Summary and Indexing")
    print()
    
    if args.transport == "http":
        print(f"🌐 Server will run on HTTP transport at http://localhost:{args.port}")
        print("   You can test it with curl or web browser")
        if args.reload:
            print("   Auto-reload enabled")
    else:
        print("💡 Server will run on stdio transport for MCP clients")
    
    print("   Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        if args.reload:
            repo_root = Path(__file__).resolve().parent.parent
            server_spec = f"{repo_root / 'src/myagent/mcp_server.py'}:mcp"
            cmd = [
                "uv",
                "run",
                "fastmcp",
                "run",
                server_spec,
                "--transport",
                "http",
                "--port",
                str(args.port),
                "--reload",
            ]
            subprocess.run(cmd, check=True, cwd=str(repo_root))
            return

        from myagent.mcp_server import main as server_main
        server_main(transport=args.transport, port=args.port)
    except KeyboardInterrupt:
        print("\n👋 Resume Agent MCP Server stopped.")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
