# 智能简历定制助手

这是一个提供简历管理工具的 MCP 服务器，聚合了简历版本管理、渲染与 PDF 生成能力，可供 MCP 客户端（如 Claude Desktop）直接调用。

## 系统要求

- Python 3.12 或更高版本
- UV 包管理器
- DEEPSEEK API TOKEN（仅需充值1美元）
- Google API Key（免费，从 Google AI Studio 获取）

## 安装步骤

1. **安装 UV**
   ```bash
   pip install uv
   ```

2. **验证 UV 安装**
   ```bash
   uv --version
   ```

3. **克隆仓库**
   ```bash
   git clone <repository-url>
   cd resume_mcp
   ```

4. **创建并激活虚拟环境**
   ```bash
   # 创建虚拟环境
   uv venv
   
   # 激活虚拟环境
   # macOS/Linux:
   source .venv/bin/activate
   # Windows:
   .venv\Scripts\activate
   ```

5. **安装依赖**
   ```bash
   # 从 pyproject.toml 安装依赖
   uv sync
   
   # 或从 requirements.txt 安装
   uv pip install -r requirements.txt
   ```

6. **配置环境变量**
   在根目录创建 `.env` 文件并设置以下环境变量：
   ```env
   GOOGLE_API_KEY=your_api_key_here  # 免费，从 Google AI Studio 获取
   OPENAI_API_KEY=your_openai_api_key_here
   DEEPSEEK_API_KEY=your_deepseek_api_key_here  # 需要充值1美元
   RESUME_DATA_DIR=./data/resumes
   RESUME_SUMMARY_PATH=./src/myagent/resume_summary.yaml
   RESUME_JD_DIR=./data/jd
   ```

7. （可选）**获取 API 密钥（仅在调用 LLM 相关工具时需要）**

   a. **Google API Key（免费）**
   - 访问 [Google AI Studio](https://makersuite.google.com/app/apikey)
   - 使用 Google 账号登录
   - 点击"Create API Key"
   - 将生成的密钥复制到 `.env` 文件中

   b. **DEEPSEEK API TOKEN**
   - 访问 [DEEPSEEK 平台](https://platform.deepseek.com/)
   - 注册并登录账号
   - 进入 API 管理页面
   - 充值1美元获取 API TOKEN
   - 将 TOKEN 添加到 `.env` 文件的 `DEEPSEEK_API_KEY` 字段

8. **启动 MCP 服务器**
   ```bash
   # HTTP 传输（便于本地调试）
   uv run python scripts/start_mcp_server.py --transport http --port 8000

   # 或使用 stdio 传输（供 MCP 客户端对接）
   uv run python scripts/start_mcp_server.py --transport stdio
   ```

## 使用示例

### 1. 基础简历操作
```python
# 读取特定简历
"read resume_tesla_ml_performance.tex"

# 读取职位描述
"read jd tesla.txt"

# 添加项目经验
"""add project experience: Parallel Prime Number Computation (MPI)
• 使用 C/C++ 和 MPI 实现分布式素数筛选算法
• 将数据分片分配给多个进程进行并行计算
• 在16节点集群上实现了近线性加速（≈15×）
• 精通进程间通信和负载均衡策略"""
```

### MCP 使用
- 参考 `docs/mcp_server.md` 与 `MCP_SETUP.md` 获取客户端连接与工具列表。

### 3. 简历定制
```python
# 根据职位描述处理和定制简历
"please process it"

# 系统将：
# 1. 分析职位描述
# 2. 匹配相关技能和经验
# 3. 定制简历内容
# 4. 生成定制版本
```

## 主要功能

- 支持多个版本的简历模板管理
- 自动分析职位描述（JD）
- 智能匹配和提取合适的简历内容
- 根据职位描述自动定制简历内容
- 支持模块化的简历结构
- 集成 LangSmith 追踪功能，方便调试和优化

## 项目结构

- `src/myagent/mcp_server.py`: MCP 服务端，暴露所有工具
- `src/myagent/tools.py`: 工具函数定义
- `src/myagent/llm_config.py`: LLM 配置（已改为按需懒加载）
- `data/resumes/`: 简历数据
- `data/jd/`: 职位描述数据

## 注意事项

- 替换 `<repository-url>` 为实际的仓库地址
- UV 比传统的 pip 安装速度更快
- 项目使用 Python 3.12
- DEEPSEEK API TOKEN 需要充值1美元
- Google API Key 可从 Google AI Studio 免费获取
- 确保所有必要的环境变量都已正确设置
- 使用前请确保有足够的 API 调用额度
- 建议在开发环境中使用 LangSmith 追踪功能进行调试 

## 工具

### RenderResumeToLaTeX
- LangChain 工具名称：`RenderResumeToLaTeX`
- Python 调用：`from myagent.tools import render_resume_to_latex_tool`
- 根据 YAML 版本输出 LaTeX 字符串。

### CompileResumePDF
- LangChain 工具名称：`CompileResumePDF`
- Python 调用：`from myagent.tools import compile_resume_pdf_tool`
- 需要 `xelatex` 与 `data/BowenResume` 中的 Awesome-CV 资源，返回 PDF 路径。

### CLI
- 打印 LaTeX：`uv run python scripts/render_resume_cli.py resume`
- 生成 LaTeX 与 PDF：
  ```bash
  uv run python scripts/render_resume_cli.py resume \
      --tex build/resume.tex \
      --pdf build/resume.pdf \
      --compile
  ```

## 测试

- 一键执行（Schema + pytest + PDF）：
  ```bash
  uv run python scripts/run_all_tests.py
  ```
- PDF 渲染单测：
  ```bash
  uv run pytest tests/test_resume_rendering.py
  ```
