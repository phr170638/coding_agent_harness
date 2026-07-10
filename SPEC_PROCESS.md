# SPEC PROCESS — Coding Agent Harness 开发过程

## 总体策略

**Spec-Driven, TDD, Phase 递进。**

先写下 SPEC.md 定义清楚"要做什么"，再拆成 PLAN.md 的 9 个 Phase，每个 Phase 内的 Task 先写失败测试（红）→ 最小实现（绿）→ 重构。每个 Phase 完成后运行全部测试确保无回归。

## Phase 0: 项目骨架

**目标**: 搭建空项目结构，配置/凭据基础模块就位。

- 初始化 `pyproject.toml`，声明全部依赖
- Pydantic Settings 配置系统：YAML 文件加载 + 环境变量覆盖
- keyring 凭据封装：`CredentialStore` 类

**关键决策**: 使用 `flat-layout` 而非 `src-layout`，`pyproject.toml` 中通过 `include = ["myagent*"]` 确保 setuptools 正确打包。

## Phase 1: LLM 抽象层

**目标**: LLM 调用可测试、可替换。

- `LLMBackend` Protocol：定义 `async decide(context, tools) -> str` 接口
- `MockLLMBackend`：预设响应列表，按序返回，支持模拟 tool_call 格式
- `AliBailianBackend`：基于 `openai` SDK 调用阿里百炼，兼容 function calling
- `PromptBuilder`：构建 system/user prompt，token 超限自动截断

**关键决策**: 用 Protocol 而非 ABC 的原因是为了最大化灵活性 — Mock 可以完全不继承任何基类。

**Bug 修复**: 阿里百炼的 function calling 返回格式中，字段名是 `"name"` 而非 OpenAI 标准的 `"action"`，在 ActionParser 中做了兼容处理。

## Phase 2: 工具系统

**目标**: 可注册、可扩展的工具分发机制。

- `Tool` dataclass + `ToolRegistry` 注册中心
- `read_file` / `write_file` 文件工具
- `run_shell` 命令执行（含超时控制）
- `run_tests` + `search_code` 测试和搜索

**关键决策**: 工具函数本身不做权限校验，所有安全检查放在 Guardrail 层 — 职责分离。

## Phase 3: 治理护栏（重点维度）

**目标**: 多层防御，代码级安全，不依赖 LLM 判断。

- `GuardrailPipeline` 链式执行，任一拦截即停止
- `PathGuardrail`: 路径沙箱，拒绝 `../` 逃逸和绝对路径
- `CommandGuardrail`: 三层防护 — 正则黑名单 → shlex 命令解析 → 白名单
- `NetworkGuardrail`: 拦截 `curl`/`wget` 等外网请求，允许 localhost
- `HITL` 状态机: `WAITING_CONFIRM → APPROVED/REJECTED`，支持超时自动拒绝

**关键决策**: 每层 Guardrail 是独立函数，输入统一为 Action 对象，输出统一为 `GuardResult(allowed, reason, risk_level)`。新增护栏只需实现协议并加入 pipeline。

## Phase 4: 反馈闭环

**目标**: 自动检测代码质量，失败时驱动 LLM 修正。

- `TestFeedbackRunner`: subprocess 调用 pytest，解析 JSON 报告
- `LintChecker`: subprocess 调用 ruff，解析 output
- `FeedbackPipeline`: 串行执行，汇总结果回灌 LLM 上下文

**Bug 修复**: `TestFeedbackRunner` 类名与 pytest 收集器冲突（pytest 将其识别为测试类），添加 `__init__` 构造函数后 pytest 不再收集。

## Phase 5: 记忆系统

**目标**: 会话内上下文 + 跨会话知识检索。

- SQLite: sessions / turns / conventions 三张表，滑动窗口对话历史
- ChromaDB: 语义向量存储，text-embedding-v3 embedding，支持相似度检索

**Bug 修复**: SQLite 在 Windows 下的文件锁问题 — 多线程访问同一数据库文件会报 `database is locked`。解决方案是持久连接 + `check_same_thread=False`。

## Phase 6: Agent 主循环

**目标**: 串联 LLM→解析→护栏→执行→反馈→记忆的完整链路。

- `AgentState`: 状态 tracking（步骤数、历史、状态）
- `StopCondition`: 最大步数 / LLM DONE 信号 / 连续失败 N 次
- `ActionParser`: JSON 模式 + function calling 模式解析，失败最多重试 2 次
- `AgentLoop`: 主循环汇编全部模块

**Bug 修复**: ActionParser 的 `_extract_json` 正则 `\{[\s\S]*\}` 无法处理嵌套花括号（如 `{"params": {"key": "value"}}`），改为括号计数法并尊重字符串边界。

## Phase 7: CLI

**目标**: Typer + Rich 的命令行入口。

- `myagent init` / `key set` / `key status` / `key clear` / `run`
- Rich Panel 渲染每步详情：工具调用、护栏检查、反馈结果
- HITL 确认用 `rich.prompt.Confirm`

## Phase 8: Docker 分发

**目标**: 容器化一键部署。

- `Dockerfile`: python:3.12-slim + git + ripgrep
- `.gitlab-ci.yml`: lint + type check + pytest
- `docker-compose.yml`: agent-api 服务 + cli profile

## Phase 9: 集成测试 + 机制演示

**目标**: 端到端验证 + 可演示脚本。

- 集成测试: MockLLMBackend 驱动完整循环，验证六维度协作
- `demo/demo_guardrail.py`: 护栏拦截危险命令
- `demo/demo_feedback.py`: 注入失败，agent 自动修正
- `demo/demo_hitl.py`: HITL 人工审批流程

## 测试统计

```
150 passed, 3 skipped (ChromaDB 集成测试需真实环境)
```

分布:
- agent: 43 tests（主循环 + 解析 + 状态 + 停机）
- llm: 31 tests（mock + bailian + prompt）
- guardrails: 28 tests（pipeline + path + command + hitl）
- tools: 22 tests（registry + file_io + shell + docker_sandbox）
- feedback: 8 tests（linter + test_runner）
- memory: 10 tests（sqlite + chroma）
- cli: 8 tests
- config: 2 tests
- credentials: 3 tests
- integration: 7 tests

## 经验教训

1. **Protocol 优于 ABC** — 对于可测试性至关重要的抽象层，用 Protocol 让 Mock 完全解耦
2. **正则解析 JSON 不可靠** — 括号计数法虽然笨重，但能处理任意嵌套
3. **SSE 事件循环让权** — `asyncio.sleep(0)` 是 Python asyncio 中让出控制权的关键
4. **SQLite + Windows = 注意文件锁** — 持久连接是唯一可靠的方案
5. **Spec 先行能减少返工** — 6 个用户故事和 7 个验收标准覆盖了所有核心路径
