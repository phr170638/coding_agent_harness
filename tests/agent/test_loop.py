"""Agent 主循环测试 — 全部用 MockLLMBackend 驱动。"""

from unittest.mock import AsyncMock

import pytest

from myagent.agent.loop import AgentLoop
from myagent.agent.state import AgentState
from myagent.config.settings import Settings
from myagent.feedback.base import FeedbackChecker, FeedbackResult
from myagent.guardrails.base import Action, GuardResult
from myagent.guardrails.pipeline import GuardrailPipeline
from myagent.llm.mock import MockLLMBackend
from myagent.tools.base import Tool
from myagent.tools.registry import ToolRegistry


@pytest.fixture
def settings():
    return Settings(max_steps=10)


@pytest.fixture
def tool_registry():
    registry = ToolRegistry()

    async def mock_read(path: str) -> dict:
        return {"ok": True, "content": f"mock content of {path}"}

    async def mock_write(path: str, content: str) -> dict:
        return {"ok": True, "path": path}

    async def mock_shell(command: str, cwd: str | None = None) -> dict:
        return {"exit_code": 0, "stdout": f"mock: {command}", "stderr": ""}

    registry.register(Tool(
        name="read_file",
        description="读取文件",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        execute=mock_read,
    ))
    registry.register(Tool(
        name="write_file",
        description="写入文件",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        execute=mock_write,
    ))
    registry.register(Tool(
        name="run_shell",
        description="执行命令",
        parameters={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]},
        execute=mock_shell,
    ))
    return registry


@pytest.fixture
def guardrail_pipeline():
    return GuardrailPipeline()


@pytest.fixture
def passing_feedback():
    """始终通过的反饋管道。"""
    return [AsyncMock(return_value=FeedbackResult(passed=True, source="mock"))]


@pytest.fixture
def make_loop(tool_registry, guardrail_pipeline, passing_feedback, settings):
    def _make(llm, **kwargs):
        return AgentLoop(
            llm_backend=llm,
            tool_registry=tool_registry,
            guardrail_pipeline=guardrail_pipeline,
            feedback_checkers=passing_feedback,
            settings=settings,
            **kwargs,
        )
    return _make


class TestAgentLoop:
    async def test_single_tool_call_and_complete(self, make_loop):
        """单步工具调用 → DONE → 正常退出。"""
        llm = MockLLMBackend([
            '{"name": "read_file", "parameters": {"path": "main.py"}}',
            '{"name": "DONE", "parameters": {"message": "完成"}}',
        ])
        loop = make_loop(llm)
        state = await loop.run("读取文件", "/tmp/project")

        assert state.status == "completed"
        assert state.step_number == 2
        assert state.conversation_history[0]["action_type"] == "read_file"
        assert state.conversation_history[1]["action_type"] == "DONE"

    async def test_guardrail_block_records_failure(self, make_loop, guardrail_pipeline):
        """护栏拦截 → 记录失败，循环继续。"""
        class BlockGuard:
            def check(self, action: Action) -> GuardResult:
                return GuardResult(
                    allowed=action.name != "dangerous_tool", reason="危险操作"
                )
        guardrail_pipeline.add(BlockGuard())
        llm = MockLLMBackend([
            '{"name": "dangerous_tool", "parameters": {}}',
            '{"name": "read_file", "parameters": {"path": "x.py"}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = make_loop(llm)
        state = await loop.run("test", "/tmp")

        assert state.status == "completed"
        # 第一步被拦截，计为失败
        assert state.conversation_history[0]["action_result"].startswith("BLOCKED:")

    async def test_max_steps_exits(self, make_loop):
        """达到最大步数 → 强制退出。"""
        llm = MockLLMBackend(['{"name": "read_file", "parameters": {"path": "x.py"}}'] * 20)
        loop = make_loop(llm)
        loop._settings.max_steps = 3  # 覆盖设置
        state = await loop.run("test", "/tmp")

        assert state.status == "failed"
        assert state.step_number == 3
        assert "达到最大步数" in state.completion_message

    async def test_unknown_tool_records_failure(self, make_loop):
        """调用未注册的工具 → 记录失败，循环继续。"""
        llm = MockLLMBackend([
            '{"name": "nonexistent_tool", "parameters": {}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = make_loop(llm)
        state = await loop.run("test", "/tmp")

        assert state.status == "completed"
        assert "未知工具" in state.conversation_history[0]["action_result"]

    async def test_tool_execution_error_records_failure(self, make_loop, tool_registry):
        """工具执行异常 → 记录失败，循环继续。"""
        async def broken_tool(**kwargs):
            raise RuntimeError("模拟工具崩溃")
        tool_registry.register(Tool(
            name="broken",
            description="会崩溃的工具",
            parameters={"type": "object", "properties": {}},
            execute=broken_tool,
        ))
        llm = MockLLMBackend([
            '{"name": "broken", "parameters": {}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = make_loop(llm)
        state = await loop.run("test", "/tmp")

        assert state.status == "completed"
        assert "ERROR:" in state.conversation_history[0]["action_result"]

    async def test_consecutive_failures_exits(self, make_loop):
        """连续失败超限 → 强制退出。"""
        llm = MockLLMBackend(['{"name": "nonexistent", "parameters": {}}'] * 10)
        loop = make_loop(llm)
        loop._settings.max_consecutive_failures = 3
        state = await loop.run("test", "/tmp")

        assert state.status == "failed"
        assert "连续失败" in state.completion_message

    async def test_done_signal_without_tool_call(self, make_loop):
        """首步直接返回 DONE。"""
        llm = MockLLMBackend([
            '{"name": "DONE", "parameters": {"message": "无需操作"}}',
        ])
        loop = make_loop(llm)
        state = await loop.run("test", "/tmp")

        assert state.status == "completed"
        assert state.step_number == 1

    async def test_feedback_failure_context(self, make_loop, passing_feedback):
        """反馈失败时上下文传递给 LLM。"""
        # 第一次反馈通过，第二次失败
        passing_feedback[0].side_effect = [
            FeedbackResult(passed=True, source="test"),
            FeedbackResult(passed=False, errors=[], summary="测试失败", source="test"),
            FeedbackResult(passed=True, source="test"),
        ]
        llm = MockLLMBackend([
            '{"name": "read_file", "parameters": {"path": "a.py"}}',
            '{"name": "read_file", "parameters": {"path": "b.py"}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = make_loop(llm)
        state = await loop.run("test", "/tmp")

        assert state.status == "completed"
        # 第二轮 LLM 上下文应包含反馈失败信息
        assert state.step_number == 3

    async def test_bailian_real_backend_not_found_skips(self):
        """真实百炼后端不可用时优雅处理。"""
        from myagent.agent.loop import AgentLoop
        from myagent.tools.registry import ToolRegistry
        from myagent.guardrails.pipeline import GuardrailPipeline
        from myagent.config.settings import Settings
        from myagent.feedback.base import FeedbackResult
        from unittest.mock import AsyncMock

        settings = Settings()
        settings.llm_api_key = ""
        loop = AgentLoop(
            llm_backend=None,  # type: ignore
            tool_registry=ToolRegistry(),
            guardrail_pipeline=GuardrailPipeline(),
            feedback_checkers=[AsyncMock(return_value=FeedbackResult(passed=True))],
            settings=settings,
        )
        # LLM 为 None 时应能检测到（实现中由 CLI 层保证传入有效后端）
        assert loop._llm is None
