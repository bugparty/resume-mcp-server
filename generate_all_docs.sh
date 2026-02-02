#!/bin/bash
#
# 一键生成 MCP 工具文档
# 这个脚本会：
# 1. 使用 fastmcp inspect 导出工具列表到 JSON
# 2. 生成 Markdown 格式的文档
# 3. 生成 HTML 格式的文档
#

set -e

echo "📚 MCP 工具文档生成器"
echo "======================"
echo ""

# 检查参数
SERVER_FILE="${1:-src/myagent/mcp_server.py}"
JSON_FILE="${2:-mcp_tools_report.json}"
MD_FILE="${3:-MCP_TOOLS.md}"
HTML_FILE="${4:-MCP_TOOLS.html}"

echo "📋 步骤 1: 使用 fastmcp inspect 导出工具列表..."
uv run fastmcp inspect "$SERVER_FILE" --format fastmcp -o "$JSON_FILE" 2>&1 | grep -v "DeprecationWarning\|UserWarning" || true
echo "✓ JSON 报告已生成: $JSON_FILE"
echo ""

echo "📝 步骤 2: 生成 Markdown 文档..."
python generate_mcp_docs.py "$JSON_FILE" "$MD_FILE"
echo ""

echo "🌐 步骤 3: 生成 HTML 文档..."
python generate_mcp_html.py "$JSON_FILE" "$HTML_FILE"
echo ""

echo "🎉 完成！"
echo "----------------"
echo "生成的文件:"
echo "  - $JSON_FILE (JSON 格式)"
echo "  - $MD_FILE (Markdown 格式)"
echo "  - $HTML_FILE (HTML 格式)"
echo ""
echo "💡 提示: 在浏览器中打开 $HTML_FILE 查看美观的文档"
