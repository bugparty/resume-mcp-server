# MCP Tools 参数统一与重命名重构计划（2026-02）

## 背景与目标
近期对 `mcp_server.py` 做了重构，但 MCP tools 的对外接口仍存在以下不一致：
- 部分工具使用 `filename` 且要求带 `.yaml` 后缀（例如 `load_complete_resume`、`list_resume_sections`）。
- 部分工具使用 `version`，部分使用 `version_name`，跨工具参数命名不一致。
- section 相关 API 同时存在 `module_path`（如 `resume/summary`）与 `(version_name, section_id)` 两种风格，易混淆且增加维护成本。
- `get_section_style` 实际返回的是“简历整体布局（section order + disabled）”，命名不贴切。

本次重构目标：
1. **统一版本参数为 `version_name`**（不带 `.yaml` 后缀）。
2. **section API 统一为 `(version_name, section_id)`**（不再接受 `module_path`）。
3. **重命名 `get_section_style` → `get_resume_layout`**，表达其返回的是整体布局。
4. **不做兼容层**：删除旧参数名/旧工具名/旧调用方式（breaking change）。
5. 修复工具层封装与底层函数签名不匹配问题，确保运行时一致。

## 设计决策（明确 Breaking）
- 仅保留 `version_name`，不再接受 `version`/`filename`。
- 仅保留 `(version_name, section_id)` 风格，不再接受 `module_path`。
- 工具名重命名不做 alias：
  - `get_section_style` 删除，新增 `get_resume_layout`。

## 目标 MCP Tool API（对外）
以下为最终希望通过 FastMCP 暴露的工具签名（均为 snake_case）：

- `load_complete_resume(version_name: str) -> str`
  - 读取 `data/resumes/{version_name}.yaml` 并渲染完整 Markdown。

- `list_resume_sections(version_name: str) -> dict`
  - 返回 section 列表（建议结构化 dict，而不是 JSON 字符串）。

- `get_resume_section(version_name: str, section_id: str) -> str`
  - 返回对应 section 的 Markdown。

- `update_resume_section(version_name: str, section_id: str, new_content: str) -> str`
  - 更新对应 section。

- `set_section_visibility(version_name: str, section_id: str, enabled: bool=True) -> dict`
  - 修改 layout 的 section_disabled，并返回更新后的 layout。

- `set_section_order(version_name: str, order: list[str]) -> dict`
  - 修改 layout 的 section_order，并返回更新后的 layout。

- `get_resume_layout(version_name: str) -> dict`
  - 返回 `{"section_order": [...], "section_disabled": {...}}`。

- `render_resume_pdf(version_name: str) -> dict`
- `submit_resume_pdf_job(version_name: str) -> dict`
- `render_resume_to_overleaf(version_name: str) -> dict`

> 说明：section_id 保持字符串类型，避免 enum 限制导致无法访问自定义 section（例如 `additional`）。

## 实现范围（文件与模块）
### 需要修改的核心文件
- `src/myagent/mcp_server.py`
  - 调整 FastMCP tool 定义与参数名。
  - 删除旧 `get_section_style`，新增 `get_resume_layout`。

- `src/myagent/tools.py`
  - Pydantic 输入模型改为 `version_name` / `section_id`。
  - StructuredTool 封装函数签名统一。
  - 修复 update_resume_section tool 与 `resume_loader.update_resume_section` 的签名错配。

- `src/myagent/resume_loader.py`
  - 提供基于 `(version_name, section_id)` 的读/写入口。
  - 将以 `filename`、`module_path` 为主的接口改造/重命名。
  - `get_section_style` 重命名为 `get_resume_layout`（或对应实现）。

### 需要同步调整的测试
- `tests/test_basic_functions.py`
- `tests/test_quick_version_workflow.py`
- `tests/test_resume_operations.py`
- 以及任何调用 `load_complete_resume("resume.yaml")` / `load_resume_section("resume/summary")` 的测试。

### 需要更新的文档/生成产物
- 重新运行 `./generate_all_docs.sh` 生成 `mcp_tools_report.json`、`MCP_TOOLS.md`、`MCP_TOOLS.html`。

## 迁移指南（给 MCP 客户端/调用方）
- `filename`（例如 `resume.yaml`）迁移为 `version_name`（例如 `resume`）。
- `module_path`（例如 `resume/summary`）迁移为：
  - `version_name="resume"`, `section_id="summary"`
- `get_section_style(version=...)` 迁移为：
  - `get_resume_layout(version_name=...)`

## 验收标准
- `pytest` 全量通过：`./.venv/bin/python -m pytest`
- `fastmcp inspect src/myagent/mcp_server.py` 输出的工具参数：
  - 不出现 `filename`、`module_path`、`version`。
  - `get_resume_layout` 存在，`get_section_style` 不存在。
- `MCP_TOOLS.md/html` 与实际接口一致。

## 实施步骤（执行顺序）
1. 修改 `resume_loader.py`：提供 version_name+section_id 的稳定接口。
2. 修改 `tools.py`：统一封装签名并修复错配。
3. 修改 `mcp_server.py`：暴露最终 MCP tool API。
4. 修改 tests：更新调用方式。
5. 运行 `pytest`，修复残余。
6. 运行 `./generate_all_docs.sh` 更新文档。
