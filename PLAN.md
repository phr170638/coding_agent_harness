# PLAN: Coding Agent Harness

> 任务粒度：每个 task 可由一个 subagent 在一次会话内完成。
> 验证步骤：先写失败测试（红）→ 最小实现使其通过（绿）→ 重构。
> `[P]` 标记表示可与其他 task 并行。

---

## 项目结构（目标）

```
coding_agent_harness/
├── myagent/
│   ├── cli/           # Typer CLI 入口
│   ├── agent/         # 主循环、状态、停机
│   ├── llm/           # LLM 抽象层
│   ├── tools/         # 工具系统
│   ├── guardrails/    # 治理护栏（重点维度）
│   ├── feedback/      # 反馈校验器
│   ├── memory/        # 记忆（SQLite + ChromaDB）
│   ├── config/        # 配置（YAML + Pydantic）
│   └── credentials/   # 凭据（keyring）
├── tests/             # 所有测试，镜像 src 结构
├── pyproject.toml
└── Dockerfile
```

---

## Phase 0: 项目骨架（无依赖）

### Task 0.1: 初始化项目结构
- **文件**: `pyproject.toml`, `myagent/__init__.py`, `tests/__init__.py`
- **要点**: 声明依赖（typer, rich, openai, chromadb, pyyaml, pydantic, pydantic-settings, keyring, docker, pytest, pytest-mock, ruff, mypy），配置 pytest
- **验证**: `pip install -e . && pytest` 能运行（0 个测试通过也算成功）

### Task 0.2: 配置系统 — Pydantic Settings [P]
- **文件**: `myagent/config/__init__.py`, `myagent/config/settings.py`
- **实现**: `Settings` 类（Pydantic Settings），从 `.myagent/config.yaml` 加载，环境变量覆盖
- **测试**: `tests/config/test_settings.py`
  - 默认值测试
  - YAML 文件加载测试
  - 环境变量覆盖测试
- **验证**: `pytest tests/config/ -v` 全部通过

### Task 0.3: 凭据存储 — keyring 封装 [P]
- **文件**: `myagent/credentials/__init__.py`, `myagent/credentials/store.py`
- **实现**: `CredentialStore` 类 — `set(key, value)`, `get(key)`, `delete(key)`, `exists(key)`
- **测试**: `tests/credentials/test_store.py`
  - mock keyring 的 set/get/delete/exists
  - get 不存在的 key 返回 None
  - set 后 get 返回原值
- **验证**: `pytest tests/credentials/ -v` 全部通过

---

## Phase 1: LLM 抽象层（Phase 0 完成后）

### Task 1.1: LLM Backend Protocol + Mock 实现
- **文件**: `myagent/llm/__init__.py`, `myagent/llm/backend.py`, `myagent/llm/mock.py`
- **实现**:
  - `LLMBackend` Protocol: `async decide(context: str, tools: list[dict]) -> str`
  - `MockLLMBackend`: 接受预设响应列表，按顺序返回，可模拟工具调用
- **测试**: `tests/llm/test_mock.py`
  - 预设响应按序返回
  - 响应耗尽后行为（循环最后一条或抛出）
  - 空响应列表行为
- **验证**: `pytest tests/llm/test_mock.py -v`

### Task 1.2: 阿里百炼 Backend
- **文件**: `myagent/llm/bailian.py`
- **实现**: `AliBailianBackend` — 用 `openai` SDK 调阿里百炼 chat API，支持 function calling 格式的工具定义
- **测试**: `tests/llm/test_bailian.py`（集成测试，无 key 时 skip）
  - 简单对话返回非空响应
  - function calling 返回 tool_call
  - 超时处理
- **验证**: 配置真实 key 后 `pytest tests/llm/test_bailian.py -v`

### Task 1.3: Prompt 构建器
- **文件**: `myagent/llm/prompt.py`
- **实现**: `build_system_prompt(config)`, `build_user_prompt(task, context)`, 工具描述 JSON schema 生成
- **测试**: `tests/llm/test_prompt.py`
  - 必需字段都存在（task、tools、project_files、conversation_history）
  - token 超限时自动截断
  - 工具 schema 格式正确
- **验证**: `pytest tests/llm/test_prompt.py -v`

---

## Phase 2: 工具系统（Phase 0 完成后，可与 Phase 1 并行）

### Task 2.1: Tool Protocol + 注册中心 [P]
- **文件**: `myagent/tools/__init__.py`, `myagent/tools/base.py`, `myagent/tools/registry.py`
- **实现**:
  - `Tool` dataclass: name, description, parameters_schema, execute 函数
  - `ToolRegistry`: 注册工具、按名称查找、列出所有工具 schema
- **测试**: `tests/tools/test_registry.py`
  - 注册/查找/列表
  - 重复注册抛异常
  - 查找不存在的返回 None

### Task 2.2: 文件工具 [P]
- **文件**: `myagent/tools/file_io.py`
- **实现**: `read_file(path)`, `write_file(path, content)` — 纯函数，不做路径校验（校验在 guardrail 层）
- **测试**: `tests/tools/test_file_io.py`
  - 读写临时文件
  - 读不存在文件抛异常
  - 二进制文件读取出错

### Task 2.3: Shell 工具 [P]
- **文件**: `myagent/tools/shell.py`
- **实现**: `run_shell(command, cwd, timeout=60)` → `ShellResult(exit_code, stdout, stderr)`
- **测试**: `tests/tools/test_shell.py`
  - 执行 `echo hello`
  - 超时终止
  - 非零退出码

### Task 2.4: 测试运行 + 代码搜索工具 [P]
- **文件**: `myagent/tools/test_runner.py`, `myagent/tools/search.py`
- **实现**:
  - `run_tests()` — subprocess 调 pytest，解析结果
  - `search_code(pattern)` — subprocess 调 `rg` 或 Python `grep`
- **测试**: 用临时项目目录，含成功的测试文件和失败的测试文件

---

## Phase 3: 治理护栏（重点维度 — 独立深入）

### Task 3.1: Guardrail Protocol + Pipeline
- **文件**: `myagent/guardrails/__init__.py`, `myagent/guardrails/base.py`, `myagent/guardrails/pipeline.py`
- **实现**:
  - `Guardrail` Protocol: `check(action) -> GuardResult(allowed: bool, reason: str)`
  - `GuardrailPipeline`: 链式执行多个护栏，任一拦截即停止
- **测试**: `tests/guardrails/test_pipeline.py`
  - 全部通过
  - 第二个护栏拦截时不执行第三个
  - 空 pipeline 全部通过

### Task 3.2: PathGuardrail
- **文件**: `myagent/guardrails/path.py`
- **实现**: 所有文件路径解析后检查是否在项目根目录内，拒绝 `../` 逃逸
- **测试**: `tests/guardrails/test_path.py`
  - 项目内路径通过
  - `../../etc/passwd` 拦截
  - 绝对路径 `/etc/passwd` 拦截
  - 符号链接逃逸（若平台支持）

### Task 3.3: CommandGuardrail（核心）
- **文件**: `myagent/guardrails/command.py`
- **实现**:
  - L1: 正则黑名单 — `rm -rf /`, `DROP TABLE`, `DELETE FROM`, `curl.*|.*sh`, `chmod 777 /`, `mkfs`
  - L2: 命令解析白名单 — 解析 shell 命令（用 `shlex`），只允许声明的安全命令
  - L3: 参数校验 — 如 `git push --force` 拦截 `--force` 参数
- **测试**: `tests/guardrails/test_command.py`
  - 至少 10 个危险命令场景，全部被拦截
  - 至少 5 个安全命令场景，全部通过
  - `rm -rf /` 被拦截
  - `rm file.txt`（项目内）通过

### Task 3.4: NetworkGuardrail
- **文件**: `myagent/guardrails/network.py`
- **实现**: 检查命令是否含 `curl`, `wget`, `nc` 等网络工具调用外网地址
- **测试**: `tests/guardrails/test_network.py`
  - `curl https://example.com` 被拦截
  - `curl http://localhost:8000` 通过（本地）
  - `ping localhost` 通过

### Task 3.5: HITL 状态机
- **文件**: `myagent/guardrails/hitl.py`
- **实现**:
  - 状态: `IDLE → WAITING_CONFIRM → APPROVED/REJECTED → IDLE`
  - `request_confirmation(action, risk_level)` — 暂停循环，等待用户输入
  - 支持超时自动拒绝
- **测试**: `tests/guardrails/test_hitl.py`
  - mock 用户输入 y/n
  - 超时后自动拒绝
  - 风险分级正确（low/medium/high/critical）

### Task 3.6: Docker 沙箱执行器
- **文件**: `myagent/tools/docker_sandbox.py`
- **实现**: 用 `docker-py` 在临时容器中执行 shell 命令，限制网络、挂载只读项目目录
- **测试**: `tests/tools/test_docker_sandbox.py`（有 Docker 环境时运行，否则 skip）
  - 容器内执行 `echo hello`
  - 容器内写文件不会影响宿主机
  - 容器超时自动杀死

---

## Phase 4: 反馈闭环（Phase 2 完成后）

### Task 4.1: Feedback Protocol + Pipeline
- **文件**: `myagent/feedback/__init__.py`, `myagent/feedback/base.py`
- **实现**:
  - `FeedbackResult`: `{passed: bool, errors: list[FeedbackError], summary: str}`
  - `FeedbackChecker` Protocol: `check(project_path) -> FeedbackResult`
  - `FeedbackPipeline`: 串行执行多个 checker，汇总结果

### Task 4.2: TestRunner 反馈
- **文件**: `myagent/feedback/test_runner.py`
- **实现**: 调 `pytest --json-report` 解析 JSON 输出为 `FeedbackResult`
- **测试**: 准备临时项目，放成功测试和失败测试，分别验证解析结果

### Task 4.3: LintChecker 反馈 [P]
- **文件**: `myagent/feedback/linter.py`
- **实现**: 调 `ruff check --output-format=json` 解析结果
- **测试**: 准备含 lint 错误的临时文件，验证错误被正确捕获和格式化

---

## Phase 5: 记忆系统（Phase 2 完成后，可与 Phase 4 并行）

### Task 5.1: SQLite 会话存储
- **文件**: `myagent/memory/__init__.py`, `myagent/memory/sqlite.py`
- **实现**: `SessionStore` — 创建/查询会话、记录轮次、存储项目约定
- **测试**: `tests/memory/test_sqlite.py`
  - CRUD 操作
  - 滑动窗口（max_conversation_turns）
  - 跨会话查询项目约定

### Task 5.2: ChromaDB 知识存储 [P]
- **文件**: `myagent/memory/chroma.py`
- **实现**: `KnowledgeStore` — 语义搜索项目约定和历史决策，embedding 用阿里 text-embedding-v3
- **测试**: `tests/memory/test_chroma.py`
  - 索引一条知识后能搜到
  - 更新已有条目
  - embedding 调用失败时优雅降级

---

## Phase 6: Agent 主循环（Phase 1-5 完成后）

### Task 6.1: AgentState + 停机判断
- **文件**: `myagent/agent/__init__.py`, `myagent/agent/state.py`, `myagent/agent/stop.py`
- **实现**:
  - `AgentState` dataclass: task, context, step_count, history, memory, config
  - `StopCondition` — 达到最大步数、LLM 响应 DONE、连续失败 N 次
- **测试**: `tests/agent/test_state.py`, `tests/agent/test_stop.py`
  - 正常状态不触发停机
  - 达到 max_steps 触发
  - 连续失败触发

### Task 6.2: Action 解析器
- **文件**: `myagent/agent/parser.py`
- **实现**: 解析 LLM 输出的 JSON/function call 为结构化 `Action` 对象
  - 支持 JSON mode 解析
  - 支持 function calling 格式
  - 解析失败重试（最多 2 次）
- **测试**: `tests/agent/test_parser.py`
  - 正常 JSON 解析
  - 带 markdown 代码块的 JSON
  - 非法 JSON → 重试 → 最终失败

### Task 6.3: 主循环
- **文件**: `myagent/agent/loop.py`
- **实现**:
  ```
  while not should_stop(state):
      context = build_context(state)
      raw_response = await llm.decide(context, tools_schema)
      action = parse_action(raw_response)
      guard_result = guardrail_pipeline.check(action)
      if guard_result.blocked:
          state.add_feedback(blocked=True, reason=guard_result.reason)
          continue
      result = await tool_dispatcher.execute(action)
      feedback = feedback_pipeline.check(project_path)
      state.add(result, feedback)
      memory.record(action, result, feedback)
  ```
- **测试**: `tests/agent/test_loop.py`（全部用 MockLLMBackend）
  - 单步工具调用成功
  - 护栏拦截 → 循环继续
  - 反馈失败 → LLM 收到错误信息 → 修正
  - DONE 信号 → 正常退出
  - 达到最大步数 → 强制退出

---

## Phase 7: CLI（Phase 0 完成后即可开始，逐步补全）

### Task 7.1: CLI 骨架 + init 命令
- **文件**: `myagent/cli/__init__.py`, `myagent/cli/main.py`
- **实现**: Typer app，`myagent init` 生成 `.myagent/config.yaml` 默认配置
- **验证**: `myagent init` 生成配置文件，内容校验正确

### Task 7.2: key 子命令
- **文件**: `myagent/cli/key.py`
- **实现**: `key set`（getpass 隐藏输入→keyring）、`key status`（显示状态）、`key clear`
- **验证**: 手动测试三个命令

### Task 7.3: run 命令 + Rich 渲染
- **文件**: `myagent/cli/run.py`
- **实现**:
  - `myagent run "task"` 启动完整 agent 循环
  - Rich Panel 显示每步：工具调用、护栏检查、反馈结果
  - spinner 显示 LLM 等待
  - HITL 确认用 `rich.prompt.Confirm`
- **验证**: mock LLM 下运行一个简单任务，终端输出格式正确

---

## Phase 8: Docker 分发

### Task 8.1: Dockerfile
- **文件**: `Dockerfile`
- **实现**: `python:3.12-slim` 基础镜像，安装依赖，ENTRYPOINT 指向 `myagent`
- **验证**: `docker build -t myagent . && docker run --rm myagent --help`

### Task 8.2: CI 配置
- **文件**: `.gitlab-ci.yml`
- **实现**: unit-test job，含 lint + type check + pytest
- **验证**: CI 绿

---

## Phase 9: 集成测试 + 机制演示

### Task 9.1: 端到端集成测试
- **文件**: `tests/integration/test_full_loop.py`
- **实现**: MockLLMBackend 驱动完整循环，验证六维度协作
- **验证**: `pytest tests/integration/ -v`

### Task 9.2: 机制演示脚本
- **文件**: `demo/`
- **实现**:
  1. `demo_guardrail.py` — 护栏拦截危险命令
  2. `demo_feedback.py` — 注入失败，agent 修正
  3. `demo_hitl.py` — HITL 人工审批流程
- **验证**: 每个脚本可独立运行，输出清晰

---

## 依赖图

```
Phase 0 (骨架) ──→ Phase 1 (LLM) ──┐
                 ├── Phase 2 (工具) ──┤
                 │                    ├──→ Phase 6 (主循环) ──→ Phase 9 (集成)
                 ├── Phase 3 (护栏) ──┤
                 │                    │
                 ├── Phase 4 (反馈) ──┤
                 └── Phase 5 (记忆) ──┘
                                    │
Phase 0 ──→ Phase 7 (CLI) ─────────┘

Phase 8 (分发) — 开发全程渐进，CI 在 Phase 0 即配置

Phase 3 (护栏) 内部 Task 3.1→3.2→3.3→3.4→3.5→3.6 线性递进（每层依赖上层）
```

## 并行建议

- Phase 1/2/3/4/5 可跨 worktree 并行开发（接口已在上层协议定义好）
- 每个 Phase 内部标记 `[P]` 的 task 可并行
- CLI (Phase 7) 可随骨架完成后即启动，逐步集成新模块

---

*下一步：git worktree 创建、subagent 派发、逐 task TDD 推进。*
