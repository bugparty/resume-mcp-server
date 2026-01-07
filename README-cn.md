# 智能简历定制助手

## 🤖 什么是智能简历定制助手？

智能简历定制助手是一个基于 MCP (Model Context Protocol) 协议的简历管理工具，让你能够在 Claude Desktop、ChatGPT 等 AI 客户端中直接管理和优化你的简历。

### 🎯 它能帮你做什么？

**📝 智能简历管理**
- 自动读取和分析你的简历内容
- 支持多个简历版本，轻松切换和比较
- 实时预览简历效果，所见即所得

**🎯 精准职位匹配**
- 上传职位描述，自动分析关键要求
- 智能推荐简历优化建议
- 一键生成针对特定职位的定制简历

**📄 专业PDF输出**
- 自动生成精美的PDF简历
- 支持自定义模板和格式
- 确保格式规范，适合直接投递

**🔄 无缝AI集成**
- 在 Claude Desktop 中直接操作
- 支持 ChatGPT 开发者模式
- 通过自然语言指令完成所有操作

### 💡 典型使用场景

1. **求职准备**：针对不同公司定制简历版本
2. **简历优化**：基于职位要求调整内容和关键词
3. **格式转换**：从Word/PDF转换为结构化数据，便于管理
4. **批量处理**：快速生成多个版本的简历

## 🚀 快速开始

### 选项1：Docker部署（推荐）

使用Docker可以最快上手，几分钟内即可使用：

```bash
# 构建镜像
docker build -t resume-mcp:latest .

# 运行并自动创建Cloudflare隧道（推荐：挂载数据目录保持持久化）
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/templates:/app/templates" \
  --env-file ./.env \
  resume-mcp:latest
```

容器会自动创建公网URL供ChatGPT集成使用。详细说明请参见 [Docker部署指南](./DOCKER-cn.md)。

### 选项2：本地环境搭建

1. **克隆仓库并设置环境**
   ```bash
   git clone <repository-url>
   cd resume_mcp
   uv venv && source .venv/bin/activate
   uv sync
   ```

2. **配置环境变量**
   ```bash
   cp sample.env .env
   # 编辑.env文件，填入你的API密钥
   ```

3. **安装XeLaTeX**（用于PDF生成）
   - macOS: `brew install --cask mactex-no-gui`
   - Ubuntu: `sudo apt-get install texlive-xetex texlive-latex-recommended`
   - 完整安装说明请参见 [MCP配置指南](./MCP_SETUP_cn.md)

4. **启动MCP服务器**
   ```bash
   # HTTP模式（用于测试）
   uv run python scripts/start_mcp_server.py --transport http --port 8000
   
   # STDIO模式（用于Claude Desktop）
   uv run python scripts/start_mcp_server.py --transport stdio
   ```

## 📚 文档导航

- **[MCP配置指南](./MCP_SETUP_cn.md)** - 详细的MCP服务器配置和客户端连接
- **[用户使用手册](./MCP_USER_MANUAL_cn.md)** - 工具使用指南和典型工作流
- **[Docker部署指南](./DOCKER-cn.md)** - Docker部署和云访问配置
- **[简历版本管理](./docs/resume_version_management.md)** - 简历版本管理

## 🛠️ 开发相关

### 测试
```bash
# 运行所有测试
uv run python scripts/run_all_tests.py

# 运行特定测试
uv run pytest tests/test_resume_rendering.py
```

### CLI工具
```bash
# 生成LaTeX
uv run python scripts/render_resume_cli.py resume

# 生成PDF
uv run python scripts/render_resume_cli.py resume --tex build/resume.tex --pdf build/resume.pdf --compile
```

## 📋 系统要求

- Python 3.12+
- UV包管理器
- XeLaTeX（用于PDF生成）

## 🚀 立即开始

无论你是求职者、HR还是开发者，都能快速上手：
- **普通用户**：使用Docker一键部署，5分钟即可使用
- **开发者**：本地环境搭建，完全控制配置和定制

详细的安装说明和故障排查，请参见 [MCP配置指南](./MCP_SETUP_cn.md)。