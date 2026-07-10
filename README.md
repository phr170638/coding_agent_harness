# Coding Agent Harness

**Agent = LLM + Harness** — 从零实现的编码智能体内核。

LLM 只负责"决定下一步做什么"，Harness（纯确定性代码）负责工具分发、治理护栏、反馈闭环、记忆管理、配置驱动的全部工程逻辑。

## 核心理念

市面上的编码 agent（Claude Code、Cursor、Copilot）是黑盒系统，开发者无法控制其主循环、治理策略和反馈机制。本项目构建一个**可独立验证、可测试、可定制**的 agent 内核：

- **自主循环** — 不是对 LangChain/AutoGen 的封装，而是从零实现的主循环
- **深度治理** — 6 层护栏叠加（正则→白名单→参数校验→Docker沙箱→分级审批→审计），不依赖 LLM 提示词
- **闭环反馈** — pytest + ruff + mypy 三方反馈自动驱动修正
- **确定性可测** — MockLLMBackend 支持无网络、无 LLM 的全链路确定性测试

## 架构

```
┌─────────────────────────────────────────────────────┐
│                  CLI (Typer + Rich)                   │
│   myagent init | key set | run "task"               │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                  Agent Main Loop                     │
│  build_context → llm.decide → parse_action           │
│     ↑                                    ↓           │
│  feedback ← execute ← guardrail_check ←─┘           │
│     │                                                  │
│     └──────────→ memory.record                        │
└──────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │
┌──────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌──▼──────────┐
│  Tools  │ │Guardrail│ │Feedback│ │   Memory     │
│ File I/O│ │Path     │ │pytest  │ │ SQLite       │
│ Shell   │ │Command  │ │ruff    │ │ ChromaDB     │
│ Git     │ │Network  │ │        │ │              │
│ Search  │ │HITL     │ │        │ │              │
└─────────┘ └─────────┘ └────────┘ └──────────────┘
```

## 快速开始

### 环境要求

- Python 3.12+
- 阿里百炼 API Key（[申请地址](https://bailian.console.aliyun.com/)）

### 安装

```bash
git clone <repo-url>
cd coding_agent_harness

# 使用 uv 管理依赖
uv sync
uv run myagent --help
```

### 配置 API Key

```bash
# 交互式录入（存入系统钥匙串，不落盘）
uv run myagent key set

# 查看状态
uv run myagent key status
```

### 运行任务

```bash
# CLI 模式
uv run myagent run "创建一个 hello.py，输出 Hello World"

# WebUI 模式
uv run myagent-server
# 浏览器打开 http://localhost:8000
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `myagent init` | 初始化项目配置 `.myagent/config.yaml` |
| `myagent key set` | 交互式录入 API Key（隐藏输入） |
| `myagent key status` | 查看 Key 是否已配置 |
| `myagent key clear` | 清除已存储的 Key |
| `myagent run "<task>"` | 启动 agent 主循环执行编码任务 |

## 配置

编辑 `.myagent/config.yaml`：

```yaml
llm:
  provider: aliyun_bailian
  model: qwen-turbo

tools:
  shell_enabled: true
  shell_sandbox: docker

guardrails:
  command_blacklist:
    - "rm -rf /"
    - "DROP TABLE"
    - "curl.*|.*sh"
  require_confirm: true

feedback:
  run_tests: true
  run_lint: true

memory:
  max_conversation_turns: 20
```

## Docker

```bash
# 构建并启动 API 服务
docker compose up -d

# CLI 模式
docker compose --profile cli run --rm cli run "任务描述"
```

## 测试

```bash
uv run pytest -v          # 150 tests
uv run ruff check .       # Lint
uv run mypy myagent/      # Type check
```

## 项目结构

```
coding_agent_harness/
├── myagent/
│   ├── agent/         # 主循环、状态机、停机判断、Action 解析
│   ├── api/           # FastAPI + SSE WebUI 后端
│   ├── cli/           # Typer CLI 入口
│   ├── config/        # Pydantic Settings 配置系统
│   ├── credentials/   # keyring 凭据管理
│   ├── feedback/      # pytest + ruff 反馈闭环
│   ├── guardrails/    # Path/Command/Network/HITL 治理护栏
│   ├── llm/           # LLM 抽象层（Mock + 阿里百炼 + Prompt 构建）
│   ├── memory/        # SQLite + ChromaDB 记忆系统
│   └── tools/         # 文件/Shell/搜索/测试/Docker沙箱 工具系统
├── frontend/
│   └── index.html     # WebUI 前端页面
├── tests/             # 150 个测试，镜像 src 结构
├── demo/              # 机制演示脚本
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── SPEC.md            # 需求规格说明
├── PLAN.md            # 实现计划
└── README.md
```

## 技术栈

| 层 | 选型 |
|----|------|
| 语言 | Python 3.12+ |
| CLI 框架 | Typer + Rich |
| LLM 接入 | 阿里百炼 qwen-turbo (OpenAI 兼容 API) |
| Embedding | text-embedding-v3 |
| 向量存储 | ChromaDB |
| 结构化存储 | SQLite |
| 沙箱 | Docker SDK (`docker-py`) |
| 凭据 | keyring |
| 配置 | YAML + Pydantic Settings |
| Web 服务 | FastAPI + SSE |
| 测试 | pytest + pytest-mock + pytest-asyncio |
| Lint/Type | ruff + mypy |

**不引入**: LangChain、Redis、AutoGen — 核心循环全部自己实现。
