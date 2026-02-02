# MCP 工具文档生成器

这个目录包含用于自动生成 MCP 工具文档的工具和脚本。

## 🚀 快速开始

### 一键生成所有文档

最简单的方式是运行一键脚本：

```bash
./generate_all_docs.sh
```

这会自动生成三种格式的文档：
- `mcp_tools_report.json` - JSON 格式的原始数据
- `MCP_TOOLS.md` - Markdown 格式的文档
- `MCP_TOOLS.html` - HTML 格式的美观文档（推荐在浏览器中查看）

### 手动分步生成

如果你需要更多控制，可以分步执行：

#### 1. 导出工具列表到 JSON

```bash
uv run fastmcp inspect src/myagent/mcp_server.py --format fastmcp -o mcp_tools_report.json
```

#### 2. 生成 Markdown 文档

```bash
python generate_mcp_docs.py mcp_tools_report.json MCP_TOOLS.md
```

#### 3. 生成 HTML 文档

```bash
python generate_mcp_html.py mcp_tools_report.json MCP_TOOLS.html
```

## 📋 工具说明

### `fastmcp inspect`

FastMCP 提供的内置工具，用于检查 MCP 服务器并导出工具信息。

**基本用法：**
```bash
uv run fastmcp inspect <server_file>
```

**导出 JSON：**
```bash
uv run fastmcp inspect <server_file> --format fastmcp -o output.json
```

**参数：**
- `--server-spec`: 要检查的 Python 文件
- `--format, -f`: 输出格式（fastmcp 或 mcp）
- `--output, -o`: 输出文件路径

### `generate_mcp_docs.py`

将 JSON 报告转换为 Markdown 文档。

**用法：**
```bash
python generate_mcp_docs.py <json_file> [output_file]
```

**示例：**
```bash
python generate_mcp_docs.py mcp_tools_report.json MCP_TOOLS.md
```

**特性：**
- 自动分类工具（只读 / 写入）
- 显示所有参数及其类型、默认值
- 清晰的格式和结构

### `generate_mcp_html.py`

将 JSON 报告转换为美观的 HTML 文档。

**用法：**
```bash
python generate_mcp_html.py <json_file> [output_file]
```

**示例：**
```bash
python generate_mcp_html.py mcp_tools_report.json MCP_TOOLS.html
```

**特性：**
- 响应式设计，适配各种屏幕
- 现代化的渐变配色
- 卡片式布局，易读性强
- 区分只读和写入工具
- 显示工具数量统计
- 在浏览器中打开查看效果最佳

## 📦 自定义使用

### 生成其他 MCP 服务器的文档

如果你有其他 MCP 服务器，只需修改 `generate_all_docs.sh` 脚本中的服务器路径：

```bash
./generate_all_docs.sh path/to/your/mcp_server.py
```

### 自定义输出文件名

```bash
# 生成到自定义位置
python generate_mcp_docs.py input.json output.md
python generate_mcp_html.py input.json output.html
```

## 📝 生成的文档内容

生成的文档包含以下信息：

### 摘要
- 总工具数量
- 只读工具数量
- 写入工具数量
- Prompt 数量
- Template 数量

### 工具详情（每个工具）
- 工具名称
- 描述
- 参数列表
  - 参数名称
  - 参数类型
  - 是否必需
  - 默认值

### Prompts
- Prompt 名称
- Prompt 描述

### Templates
- Template 名称
- URI 模板
- Template 描述

## 🎯 使用场景

1. **团队协作**：将生成的文档分享给团队成员，方便他们了解可用的 MCP 工具
2. **API 文档**：作为 MCP 服务的官方 API 文档
3. **版本控制**：将文档纳入版本控制，记录不同版本的 API 变更
4. **自动化**：集成到 CI/CD 流程中，每次代码变更时自动更新文档

## 📄 文件说明

- `generate_all_docs.sh` - 一键生成所有文档的 Shell 脚本
- `generate_mcp_docs.py` - 生成 Markdown 文档的 Python 脚本
- `generate_mcp_html.py` - 生成 HTML 文档的 Python 脚本
- `mcp_tools_report.json` - JSON 格式的工具报告（生成时自动创建）
- `MCP_TOOLS.md` - Markdown 格式的文档（生成时自动创建）
- `MCP_TOOLS.html` - HTML 格式的文档（生成时自动创建）

## 🤝 贡献

如果你有改进建议或发现问题，欢迎提交 Issue 或 Pull Request。

## 📄 许可

与主项目保持一致。
