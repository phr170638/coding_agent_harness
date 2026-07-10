# Agent Log — 开发日志

## 关键 Bug 修复记录

### 1. ActionParser 嵌套 JSON 解析失败

**现象**: LLM 返回 `{"action": "write_file", "parameters": {"path": "a.py", "content": "print(1)"}}` 时，正则 `\{[\s\S]*\}` 只能匹配到第一个 `}`，无法处理嵌套花括号。

**修复**: 用括号计数法重写 `_extract_json`，遍历字符串时追踪花括号嵌套深度，同时跳过字符串字面量内的花括号。

**文件**: `myagent/agent/parser.py`

### 2. 阿里百炼 Function Calling 字段名不匹配

**现象**: 阿里百炼的 tool_calls 返回格式中，函数名在 `"name"` 字段，而 ActionParser 期望的是 `"action"` 字段。

**修复**: 在 `AliBailianBackend` 中将 API 返回的 `"name"` 映射为内部使用的 `"action"`。

**文件**: `myagent/llm/bailian.py`

### 3. SSE 事件循环卡住

**现象**: FastAPI SSE 端点中，`on_event` 回调向 `asyncio.Queue` 放入事件后，SSE 生成器无法及时获取。

**根因**: `asyncio.Queue.put()` 不会自动让出事件循环控制权，导致生成器协程饥饿。

**修复**: 在 `on_event` 的 `queue.put()` 后添加 `await asyncio.sleep(0)`，显式让出控制权。

**文件**: `myagent/api/server.py`

### 4. SQLite Windows 文件锁

**现象**: 在 Windows 上多线程访问 ChromaDB 底层 SQLite 时报 `database is locked`。

**修复**: 持久化单连接 + `check_same_thread=False`，所有数据库操作共享同一连接。

**文件**: `myagent/memory/sqlite.py`

### 5. flat-layout 打包失败

**现象**: `pyproject.toml` 配置 `[tool.setuptools.packages.find]` 时，setuptools 找不到 `myagent` 包。

**修复**: 添加 `include = ["myagent*"]` 显式声明包位置。

**文件**: `pyproject.toml`

### 6. PytestCollectionWarning — TestFeedbackRunner

**现象**: pytest 将 `TestFeedbackRunner` 类误识别为测试类并发出 CollectionWarning。

**修复**: 给 `TestFeedbackRunner` 添加 `__init__` 构造函数，pytest 不再收集含构造的类。

**文件**: `myagent/feedback/test_runner.py`

## 技术决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-07-09 | Protocol 替代 ABC | Mock 不需要继承基类，解耦更彻底 |
| 2026-07-09 | 阿里百炼 qwen-turbo 为主模型 | 中文能力强，兼容 OpenAI SDK |
| 2026-07-09 | Docker 沙箱异步回退 subprocess | Windows 无 Docker 环境时自动降级 |
| 2026-07-09 | 护栏用正则+shlex，不用 LLM | 安全策略必须是确定性代码，不可靠给 LLM |
| 2026-07-09 | YAML 配置 + 环境变量覆盖 | Pydantic Settings 原生支持，优先级明确 |
| 2026-07-09 | 前端内嵌在 server.py | 初期快速迭代，Phase 完成后抽到独立文件 |
| 2026-07-10 | 前端抽到 frontend/index.html | 职责分离，方便后续独立开发和部署 |

## 后续计划

- [ ] Cold-start 验证：换一个 agent 从零搭建环境
- [ ] GitHub 仓库 + PR workflow
- [ ] REFLECTION.md：课程反思文档（用户自行撰写）
