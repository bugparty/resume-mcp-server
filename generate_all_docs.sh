#!/bin/bash
#
# Generate All MCP Tools Documentation
# This script will:
# 1. Export tool list to JSON using fastmcp inspect
# 2. Generate Markdown format documentation
# 3. Generate HTML format documentation
#

set -e

echo "📚 MCP Tools Documentation Generator"
echo "======================"
echo ""

# Check arguments
SERVER_FILE="${1:-src/myagent/mcp_server.py}"
JSON_FILE="${2:-mcp_tools_report.json}"
MD_FILE="${3:-MCP_TOOLS.md}"
HTML_FILE="${4:-MCP_TOOLS.html}"

echo "📋 Step 1: Exporting tool list using fastmcp inspect..."
uv run fastmcp inspect "$SERVER_FILE" --format fastmcp -o "$JSON_FILE" 2>&1 | grep -v "DeprecationWarning\|UserWarning" || true
echo "✓ JSON report generated: $JSON_FILE"
echo ""

echo "📝 Step 2: Generating Markdown documentation..."
python generate_mcp_docs.py "$JSON_FILE" "$MD_FILE"
echo ""

echo "🌐 Step 3: Generating HTML documentation..."
python generate_mcp_html.py "$JSON_FILE" "$HTML_FILE"
echo ""

echo "🎉 Done!"
echo "----------------"
echo "Generated files:"
echo "  - $JSON_FILE (JSON format)"
echo "  - $MD_FILE (Markdown format)"
echo "  - $HTML_FILE (HTML format)"
echo ""
echo "💡 Tip: Open $HTML_FILE in a browser to view the beautiful documentation"
