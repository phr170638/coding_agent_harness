# SPEC: Coding Agent Harness

> Spec-Driven, Subagent-Built, Human-Owned.

## 1. 问题陈述

### 要解决的问题

当前市面上的编码智能体（Claude Code、Cursor、GitHub Copilot 等）是黑盒系统——用户无法控制其主循环逻辑、治理策略、反馈机制和工具分发规则。开发者如果想定制一个符合自己团队规范的编码 agent，要么只能通过提示词"请求"LLM 遵守规则（不可靠），要么直接使用现成 agent 框架的高层封装（LangChain AgentExecutor、AutoGen 等），失去对核心机制的控制。

### 目标用户

- 想深入理解 agent 工程原理的软件工程师 / 学生
- 需要对编码 agent 行为做精细化治理的团队（安全策略、代码规范强制）
- 需要可审计、可测试的 agent 系统的场景

### 为什么值得做

本项目构建一个**从零实现的 Coding Agent Harness**：Agent = LLM + Harness。LLM 只负责"决定下一步做什么"，harness 负责其余所有工程——工具分发、治理护栏、反馈闭环、记忆管理、配置驱动。它不是对现成框架的封装，而是一个可独立验证、可测试、可定制的 agent 内核。

---

## 2. 用户故事

| ID | 用户 | 故事 | 验收条件 |
|----|------|------|----------|
| US1 | 开发者 | 作为开发者，我可以通过 CLI 输入自然语言编码任务，让 agent 自动完成代码修改 | 给定一个编程任务描述，agent 能读取项目文件、生成代码、写入文件 |
| US2 | 开发者 | 作为开发者，agent 修改代码后自动运行测试，如果失败则根据错误信息自我修正 | 注入一个会失败的测试，agent 运行测试后识别失败，修正代码使测试通过 |
| US3 | 安全工程师 | 作为安全工程师，当 agent 尝试执行危险命令时，系统应拦截并等待我确认 | `rm -rf /`、`DROP TABLE` 等命令被护栏拦截，无人工确认不执行 |
| US4 | 开发者 | 作为开发者，我可以通过 YAML 配置文件定义项目约定和安全策略 | 修改配置文件后，agent 行为随之改变（如工具白名单、代码规范） |
| US5 | 开发者 | 作为开发者，agent 应该记住我告诉它的项目约定，在后续对话中遵守 | 告知 agent "本项目使用 pytest 而非 unittest"后，它生成的测试代码使用 pytest |
| US6 | 运维 | 作为运维人员，我可以通过 Docker 一键部署 agent，并在容器内安全配置 API key | `docker build && docker run` 后 agent 可正常工作，key 不暴露在镜像或命令行中 |

---

## 3. 功能规约

### 3.1 CLI 入口

- `myagent init` — 初始化项目配置，生成 `.myagent/config.yaml`
- `myagent key set` — 交互式录入阿里百炼 API key（隐藏输入），存入系统钥匙串
- `myagent key status` — 查看 key 是否已配置（不回显明文）
- `myagent key clear` — 清除已存储的 key
- `myagent run "<任务描述>"` — 启动 agent 主循环，执行编码任务

### 3.2 Agent 主循环

```
1. 构建上下文（任务 + 项目文件 + 记忆 + 对话历史）
2. 调用 LLM 决策下一步动作
3. 解析 LLM 输出为结构化 Action
4. 治理护栏检查 Action
   ├── 危险 → 拦截 + 等待人工确认（HITL）
   └── 安全 → 继续
5. 工具分发执行 Action
6. 反馈校验器评估执行结果
7. 回灌结果到上下文
8. 更新记忆
9. 判断停机条件 → 继续循环或终止
```

### 3.3 工具系统

| 工具 | 函数签名 | 说明 |
|------|----------|------|
| `read_file` | `(path: str) -> str` | 读取项目文件内容 |
| `write_file` | `(path: str, content: str) -> None` | 写入文件（受路径沙箱限制） |
| `run_shell` | `(command: str) -> ShellResult` | 执行 shell 命令（受命令护栏限制） |
| `run_tests` | `() -> TestReport` | 运行项目测试套件，返回结构化结果 |
| `search_code` | `(pattern: str) -> list[Match]` | 在项目中搜索代码模式 |
| `git_diff` | `() -> str` | 查看当前变更 |

### 3.4 治理护栏（重点维度）

```
GuardrailPipeline
  ├── PathGuardrail      — 所有文件操作限制在项目目录内
  ├── CommandGuardrail   — 黑名单拦截（rm -rf, DROP TABLE, curl | bash 等）
  ├── NetworkGuardrail   — 禁止对外网络请求（curl, wget 到外网）
  └── HITLGate           — 危险级别操作暂停循环，终端等待用户 y/n 确认
```

- 危险命令识别用**正则匹配 + 命令解析**，不依赖 LLM 判断
- 每个护栏是独立函数，输入 Action，输出 `(allowed: bool, reason: str)`
- HITL 状态机：`WAITING_CONFIRM → (approved|rejected) → RESUME`

### 3.5 反馈闭环

```
FeedbackPipeline
  ├── TestRunner     — subprocess 调用 pytest，解析 JSON 报告
  ├── LintChecker    — subprocess 调用 ruff，解析输出
  └── TypeChecker    — subprocess 调用 mypy，解析输出
```

- 每个校验器返回结构化结果：`{passed: bool, errors: list[Error], summary: str}`
- 失败时错误详情完整回灌到 LLM 上下文，驱动下一轮修正

### 3.6 记忆系统

| 记忆类型 | 存储 | 检索方式 | 生命周期 |
|----------|------|----------|----------|
| 对话历史 | SQLite | 按会话 ID + 滑动窗口 | 单次会话 |
| 项目约定 | ChromaDB | 语义搜索 | 跨会话持久 |
| 历史决策 | ChromaDB | 语义搜索 | 跨会话持久 |
| 当前任务状态 | 内存 dict | 直接访问 | 单次会话 |

### 3.7 配置系统

```yaml
# .myagent/config.yaml
llm:
  provider: aliyun_bailian
  model: qwen-turbo

tools:
  shell_enabled: true
  shell_sandbox: docker    # docker / none
  file_scope: project      # project / global

guardrails:
  command_blacklist:
    - "rm -rf /"
    - "DROP TABLE"
    - "curl.*|.*sh"
  require_confirm: true

feedback:
  run_tests: true
  run_lint: true
  run_typecheck: false

memory:
  max_conversation_turns: 20
  chroma_db_path: .myagent/chroma
```

---

## 4. 非功能性需求

### 4.1 性能
- LLM 调用超时 120s
- 单次工具执行超时 60s
- 单任务最大循环步数 50 步
- 冷启动（含依赖检查）< 5s

### 4.2 安全（含凭据威胁模型）

**威胁模型：**
- 攻击者获取源码仓库访问权 → 仅暴露代码，不暴露凭据（key 不在源码中）
- 攻击者获取运行环境访问权 → keyring 存储需 OS 级别认证
- 攻击者通过 agent 工具执行恶意命令 → 护栏 + 沙箱双层防护
- API key 泄漏到日志/终端历史 → key 从不在日志中输出，`.env` 加入 `.gitignore`

**对策：**
- API key 通过 `keyring` 存系统钥匙串，不落盘
- `.env` 仅作为 fallback，`.gitignore` 排除
- CLI 的 `key set` 用 `getpass` 隐藏输入
- 日志自动脱敏 API key 模式

### 4.3 可观测性
- 每一步的 prompt token 量、LLM 延迟、工具执行耗时
- Agent 循环日志输出到终端（Rich panel 渲染）
- 可选 debug 模式输出完整 prompt/response

### 4.4 可用性
- 单命令安装：`pip install` 或 `docker run`
- CLI help 完整：每个子命令有 `--help`
- 错误信息指向明确（"API key 未配置，请运行 myagent key set"）

---

## 5. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    CLI (Typer)                       │
│  myagent init | key set | run "task"                │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                  Agent Main Loop                     │
│                                                      │
│  build_context → llm.decide → parse_action           │
│     ↑                                    ↓           │
│  feedback ← execute ← guardrail_check ←─┘           │
│     │                                                  │
│     └──────────→ memory.record                        │
└──────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │
┌──────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌──▼──────────┐
│  Tools  │ │Guardrail│ │Feedback│ │   Memory     │
│         │ │         │ │        │ │              │
│ File I/O│ │Path     │ │pytest  │ │ SQLite       │
│ Shell   │ │Command  │ │ruff    │ │ ChromaDB     │
│ Git     │ │Network  │ │mypy    │ │ (sentence-   │
│ Search  │ │HITL     │ │        │ │  transformers│
└─────────┘ └─────────┘ └────────┘ └──────────────┘
       │          │          │          │
┌──────▼──────────▼──────────▼──────────▼──────────────┐
│               LLM Backend (Protocol)                  │
│  ┌──────────────────┐  ┌──────────────────────┐      │
│  │ AliBailianBackend│  │   MockLLMBackend     │      │
│  │ (真实 API 调用)   │  │ (确定性测试用)        │      │
│  └──────────────────┘  └──────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

---

## 6. 数据模型

### SQLite 表结构

```sql
-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    task_description TEXT NOT NULL,
    project_path TEXT NOT NULL,
    status TEXT NOT NULL,  -- running, completed, failed, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话轮次表
CREATE TABLE turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    step_number INTEGER NOT NULL,
    role TEXT NOT NULL,  -- user, assistant, tool
    content TEXT NOT NULL,
    action_type TEXT,    -- read_file, write_file, run_shell, etc.
    action_result TEXT,
    feedback_passed BOOLEAN,
    token_count INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目约定表
CREATE TABLE conventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    source TEXT,  -- user_input / agent_discovered
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ChromaDB Collection

| Collection | 存储内容 | 维度 |
|------------|----------|------|
| `project_knowledge` | 项目约定、架构决策、历史经验 | 1536 (text-embedding-v3) |

---

## 7. 领域与机制设计（Coding Agent Harness 专属）

### 7.1 领域特征分析

| 维度 | Coding 领域的特性 | 如何编码实现 |
|------|-------------------|-------------|
| **反馈信号** | 测试通过/失败、lint 错误、类型检查错误 — 客观、确定、可机器解析 | subprocess 运行工具，解析结构化输出 |
| **危险动作** | `rm -rf`、数据库删除、`curl | bash`、对外推送 | 正则 + 命令解析的白/黑名单 |
| **所需工具** | 读/写文件、执行 shell、运行测试、git 操作、代码搜索 | 每个工具是独立函数，统一通过 ToolDispatcher 调用 |
| **记忆需求** | 项目约定、历史决策、代码库结构 | ChromaDB 语义检索 + SQLite 结构化查询 |

### 7.2 重点维度：治理 / 沙箱

选择**治理与沙箱**作为重点维度。理由：

1. **天然由代码构成**：护栏是确定性函数，不依赖 LLM 的"理解"，最符合"机制是代码"的要求
2. **容易做深**：从简单黑名单 → 命令 AST 解析 → Docker 沙箱执行 → HITL 审批状态机 → 分级风险策略
3. **演示效果好**：mock LLM 下可确定性地展示拦截行为
4. **工程价值高**：这是生产级 agent 最关键的工程问题，不是"加一句提示词"能解决的

### 7.3 治理实现层次（由浅入深）

```
L1: 命令黑名单（正则匹配危险模式）
L2: 命令白名单（只允许显式声明的安全命令）
L3: 参数校验（允许 git push 但禁止 --force）
L4: Docker 沙箱（所有 shell 在容器内执行，限制网络/文件系统）
L5: 分级审批（低风险自动执行、中风险提示、高风险暂停 HITL）
L6: 审计日志（所有操作完整记录，可回溯）
```

最低实现 L1–L3，目标深入实现 L4–L6。

---

## 8. 凭据与分发设计

### 8.1 凭据方案

```
优先级: keyring (系统钥匙串) > .env (环境文件) > 交互输入
```

- `myagent key set` → `getpass` 隐藏输入 → 存入 OS 钥匙串（`keyring` 库）
- `myagent key status` → 仅显示"已配置"或"未配置"
- `.env` 作为 fallback，明确文档标注其明文风险
- `.gitignore` 排除 `.env` 及一切含 key 的文件

### 8.2 分发方案

**主方案：Docker 容器**

```bash
docker build -t myagent .
docker run -it --rm \
  -v $(pwd):/workspace \
  -v /var/run/docker.sock:/var/run/docker.sock \
  myagent run "实现一个计算器"
```

- 基础镜像：`python:3.12-slim`
- 内嵌 Docker CLI（用于沙箱容器）
- API key 首次运行时通过 `key set` 交互录入，存入容器内 keyring

**备选：pip 安装**

```bash
pip install myagent
myagent key set
myagent run "任务描述"
```

### 8.3 目标平台

- Linux（主）/ macOS（兼容）/ Windows（兼容，沙箱功能需 Docker Desktop）

---

## 9. 技术选型与理由

| 层 | 选型 | 理由 |
|----|------|------|
| 语言 | Python 3.12+ | LLM 生态最成熟，开发效率高，测试工具链完善 |
| CLI 框架 | Typer | Pydantic 同源，自动 help，类型安全 |
| 终端渲染 | Rich | 彩色输出、Markdown 面板、spinner |
| LLM SDK | `openai` Python SDK | 阿里百炼兼容 OpenAI API 格式 |
| Chat 模型 | qwen-turbo / qwen-plus | 阿里百炼，中文能力强 |
| Embedding | text-embedding-v3 | 阿里百炼，统一一套 API key |
| 向量存储 | ChromaDB | 嵌入式部署，持久化，你已有经验 |
| 结构化存储 | SQLite | 标准库，零依赖 |
| 沙箱 | Docker SDK (`docker-py`) | 真正的进程隔离，非玩具方案 |
| 凭据 | `keyring` | 跨平台 OS 钥匙串 |
| 配置 | YAML + Pydantic Settings | 声明式，校验完善 |
| 测试 | pytest + pytest-mock | Python 测试事实标准 |
| 分发 | Docker + pip | Docker 最通用，pip 方便开发者 |
| Lint/Type | ruff + mypy | 本项目自身的代码质量工具 |

**不引入的组件及理由：**
- Redis — 单用户 CLI 无并发/分布式需求，SQLite 足够
- LangChain AgentExecutor — 项目要求自己实现主循环
- FastAPI/Web 服务 — CLI 工具不需要 HTTP 服务器

---

## 10. 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|----------|
| AC1 | mock LLM 下，主循环能完成"分析→工具调用→反馈→修正"的完整闭环 | 单测 |
| AC2 | 输入危险命令 `rm -rf /`，护栏拦截且不执行 | 单测 |
| AC3 | 注入一次测试失败，agent 根据失败信息修正代码使测试通过 | 机制演示脚本 |
| AC4 | 六维度（决策/工具/记忆/治理/反馈/配置）都有可运行的最低实现 | 单测覆盖 |
| AC5 | Docker 一键启动后能完成一个真实的简单编码任务 | 集成测试 |
| AC6 | 所有核心机制可用 mock LLM 做确定性测试（不依赖网络和真实 LLM） | CI |
| AC7 | API key 不在源码、Git 历史、日志、终端输出中 | 人工检查 |

---

## 11. 风险与未决问题

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 阿里百炼 API 不兼容 OpenAI SDK 格式 | 高 | 先用 curl 验证接口，备选用 httpx 直接调 |
| Docker in Docker 权限复杂 | 中 | 优先支持 Linux，Docker 沙箱为可选特性（配置开关） |
| LLM 输出格式不稳定，解析失败 | 中 | 用 structured output（JSON mode）+ 解析失败重试 |
| 本地 sentence-transformers 模型下载慢 | 低 | 如果阿里 embedding 可用就不需要本地模型 |
| Windows 兼容性（沙箱、编码） | 中 | 主开发在 Linux/Docker，Windows 做降级处理 |

---

*下一步：进入 PLAN.md — 将上述模块分解为每步 2–5 分钟的 task 列表。*
