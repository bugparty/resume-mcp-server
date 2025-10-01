# FastMCP Resume Agent Server - 快速开始

## 🏃‍♂️ 快速启动

### 方式一：直接启动 HTTP 服务器（推荐）

\`\`\`bash
cd resume_mcp
python src/myagent/mcp_server.py
\`\`\`

服务器将在 http://localhost:8000 启动，提供 HTTP 接口。

### 方式二：使用启动脚本（STDIO 模式）适合cluade

\`\`\`bash
cd resume_mcp
uv run python scripts/start_mcp_server.py
\`\`\`

### 🌐 通过 Cloudflare 隧道对外提供服务 适合chatgpt

如果需要让 ChatGPT 等外部客户端访问，可以使用 Cloudflare 隧道：

1. **启动 MCP 服务器**：
   \`\`\`bash
   python src/myagent/mcp_server.py
   \`\`\`

2. **启动 Cloudflare 隧道**：
   \`\`\`bash
   cloudflared tunnel --url http://localhost:8000
   \`\`\`

3. **获取公网地址**：
   Cloudflare 会提供一个类似 `https://xxx.trycloudflare.com` 的公网地址

4. **ChatGPT 客户端配置**：
   - 服务器地址：使用 Cloudflare 提供的 HTTPS 地址
   - 认证方式：选择"无认证"
   - 协议：HTTP/HTTPS

### 🖥️ 在 Claude Desktop 中使用

将以下配置添加到 Claude Desktop 的 MCP 配置中：

\`\`\`json
{
  "mcpServers": {
    "resume-agent": {
      "command": "uv",
      "args": ["run", "python", "scripts/start_mcp_server.py"],
      "cwd": "/path/to/resume_mcp"
    }
  }
}
\`\`\`

## 🧪 测试服务器

### 1. 测试服务器启动
\`\`\`bash
cd resume_mcp
uv run python scripts/test_mcp_server.py
\`\`\`

### 2. HTTP 接口测试

当使用 HTTP 模式启动后，可以通过以下方式测试：

\`\`\`bash
# 测试服务器状态
curl http://localhost:8000/health

# 查看可用工具
curl http://localhost:8000/tools
\`\`\`

### 3. Cloudflare 隧道测试

\`\`\`bash
# 使用 Cloudflare 提供的地址测试
curl https://xxx.trycloudflare.com/health
\`\`\`

## 💡 使用示例

启动后，你可以在 Claude Desktop 中使用这些命令：

\`\`\`
list_resume_versions()  # 查看所有简历版本
load_complete_resume("resume.yaml")  # 加载完整简历
analyze_jd("Job description text here...")  # 分析职位描述
\`\`\`

在 ChatGPT 中通过 HTTP 接口使用：

\`\`\`json
{
  "tool": "list_resume_versions",
  "args": {}
}
\`\`\`

## 🔧 技术特点

- **零修改**：完全复用现有 tools.py 中的功能
- **双模式**：支持 STDIO 和 HTTP 两种运行模式
- **云端访问**：通过 Cloudflare 隧道支持外部客户端
- **类型安全**：保持原有的 Pydantic 模型
- **标准协议**：完全兼容 MCP 标准

## 🛠️ 配置说明

### 环境变量设置

确保已配置必要的环境变量（复制 `sample.env` 到 `.env`）：

\`\`\`bash
cp sample.env .env
# 编辑 .env 文件，设置必要的 API 密钥和路径
\`\`\`

### Cloudflare 隧道配置

如需持久化隧道，可以配置 Cloudflare 隧道：

\`\`\`bash
# 创建隧道
cloudflared tunnel create myagent-mcp

# 配置隧道
cloudflared tunnel route dns myagent-mcp myagent-mcp.yourdomain.com

# 启动隧道
cloudflared tunnel run myagent-mcp
\`\`\`

## 🐛 故障排除

### 常见问题

1. **导入错误**：确保从项目根目录运行命令
2. **端口占用**：检查 8000 端口是否被占用
3. **环境变量**：确保 `.env` 文件配置正确
4. **依赖缺失**：运行 `uv sync` 安装所有依赖

### 日志调试

\`\`\`bash
# 启动时查看详细日志
python src/myagent/mcp_server.py --verbose
\`\`\`

查看详细文档：`docs/mcp_server.md`

## 🚀 已完成设置

你的 Resume Agent 工具现在已经通过 FastMCP 暴露为 MCP 服务器！支持本地运行和通过 Cloudflare 隧道对外提供服务。

### 📁 新增文件
- `src/myagent/mcp_server.py` - MCP 服务器主文件
- `scripts/start_mcp_server.py` - 启动脚本
- `scripts/test_mcp_server.py` - 测试脚本
- `docs/mcp_server.md` - 详细文档

### 🛠️ 可用工具 (14个)

#### 简历版本管理
- `list_resume_versions` - 列出所有简历版本
- `load_complete_resume` - 加载完整简历
- `load_resume_section` - 加载特定段落
- `update_resume_section` - 更新段落内容
- `create_new_version` - 创建新版本
- `list_modules_in_version` - 列出版本中的段落
- `update_main_resume` - 更新整个简历文件

#### 职位描述分析
- `analyze_jd` - 分析职位描述
- `read_jd_file` - 读取JD文件
- `tailor_section_for_jd` - 根据JD定制简历段落

#### 简历摘要和索引
- `summarize_resumes_to_index` - 生成简历摘要索引
- `read_resume_summary` - 读取简历摘要

#### 简历渲染
- `render_resume_to_latex` - 渲染为LaTeX
- `compile_resume_pdf` - 编译为PDF
