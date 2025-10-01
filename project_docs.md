# 项目名称：智能简历模块化生成系统

## 项目目标
构建一个自动化系统，能够根据不同职位的需求（JD）智能选择和修改模块化的 LaTeX 简历，并组合成完整的定制化简历文档。

## 功能概述

- 支持模块化简历结构（每个模块一个 `.tex` 文件）
- 支持多个版本简历（如 resume_2yoe_c++、resume_frontend）
- 基于职位描述（JD）自动提取关键词和分析
- 智能定制简历内容以适应目标职位
- 支持创建新的简历版本
- 支持简历模块的浓缩和再次提取
- 支持完整的简历内容预览和编辑

## 目录结构约定

```
data/BowenResume/
├── resume/                    # 通用版本模块
│   ├── summary.tex
│   ├── projects.tex
│   ├── skills.tex
│   └── ...
├── resume_2yoe_c++/           # 特定方向模块
│   ├── summary.tex
│   ├── projects.tex
│   ├── skills.tex
│   └── ...
└── cv/                        # 更学术型模块
```

## data目录说明
data目录是我的简历，resume_xxx.tex 是我根据不同岗位做的不同版本，resume_xxx.tex 打开后，里面是\input 其他tex，用来加入不同版本的summary ,education,skills, experience等等。

## Agent 架构

使用 LangChain + 自定义工具函数组成 ReAct Agent 架构。

### 已实现的工具：
- `list_resume_versions`：列出所有可用的简历版本
- `load_resume_modules`：加载并预览特定简历版本的内容
- `load_resume_section`：加载单个模块内容
- `update_resume_section`：更新特定模块内容（带自动备份）
- `analyze_jd`：分析职位描述，提取关键信息
- `create_new_version`：创建新的简历版本
- `list_modules_in_version`：列出特定版本中的所有模块
- `tailor_section_for_jd`：根据JD定制特定模块内容
- `update_main_resume`：更新主简历文件内容
- `read_jd_file`：读取职位描述文件
- `load_complete_resume`：加载完整简历内容
- `summarize_resumes_to_index`：提取简历元数据生成轻量级索引
- `read_resume_summary`：读取轻量级的简历索引文件

## 示例调用
用户输入：
```
请根据下面的JD加载匹配 resume_2yoe_c++ 中的模块，并生成定制简历。
JD：我们希望候选人具备 C++ 项目经验，并参与过开源系统开发。
```

Agent 调用流程：
1. 使用 `analyze_jd` 分析 JD → 提取关键词和需求
2. 使用 `list_resume_versions` 查看可用版本
3. 使用 `load_resume_modules` 加载模块预览
4. 使用 `tailor_section_for_jd` 定制各个模块内容
5. 使用 `update_resume_section` 更新模块内容
6. 使用 `update_main_resume` 更新主简历文件

## 技术实现细节

- 使用 Cloudflare AI Gateway 作为 LLM 调试中间件，和加速deepseek的访问
- 使用 Jinja2 进行模板渲染
- 实现了自动备份机制，确保数据安全
- 支持模块化内容的智能定制
- 使用 YAML 格式进行简历内容的聚合和管理

## 后续拓展

- Web 界面（如 Streamlit 或 Gradio）
- 增加 Cover Letter 生成器
- 模块推荐排序优化
- 简历打分（匹配度分析）
- 支持更多简历格式（如 Markdown、HTML）
- 添加简历版本管理功能
- 实现简历内容的语义搜索

## 依赖管理

本项目使用 uv 进行包管理，请使用 `uv pip install` 安装依赖。
