"""端到端集成测试 — MockLLMBackend 驱动完整循环，验证六维度协作。"""

from unittest.mock import AsyncMock

import pytest

from myagent.agent.loop import AgentLoop
from myagent.config.settings import Settings
from myagent.feedback.base import FeedbackResult
from myagent.guardrails.command import CommandGuardrail
from myagent.guardrails.pipeline import GuardrailPipeline
from myagent.guardrails.path import PathGuardrail
from myagent.llm.mock import MockLLMBackend
from myagent.tools.base import Tool
from myagent.tools.registry import ToolRegistry


@pytest.fixture
def settings():
    return Settings(max_steps=20)


@pytest.fixture
def tool_registry():
    registry = ToolRegistry()

    async def mock_read(path: str) -> dict:
        return {"ok": True, "content": f"mock: {path}"}

    async def mock_write(path: str, content: str) -> dict:
        return {"ok": True, "path": path}

    async def mock_shell(command: str, cwd: str = "") -> dict:
        return {"exit_code": 0, "stdout": "ok", "stderr": ""}

    registry.register(Tool(
        name="read_file", description="读取文件",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        execute=mock_read,
    ))
    registry.register(Tool(
        name="write_file", description="写入文件",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        execute=mock_write,
    ))
    registry.register(Tool(
        name="run_shell", description="执行命令",
        parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        execute=mock_shell,
    ))
    return registry


@pytest.fixture
def passing_feedback():
    """始终通过的反馈管道（使用 AsyncMock 满足 FeedbackChecker Protocol）。"""
    return [AsyncMock(return_value=FeedbackResult(passed=True, source="mock"))]


class TestFullLoopIntegration:
    """六维度协作集成测试。"""

    async def test_read_then_write_then_done(self, tool_registry, passing_feedback, settings):
        """标准工作流：读取 → 写入 → 完成。"""
        llm = MockLLMBackend([
            '{"name": "read_file", "parameters": {"path": "main.py"}}',
            '{"name": "write_file", "parameters": {"path": "main.py", "content": "x=1"}}',
            '{"name": "DONE", "parameters": {"message": "完成"}}',
        ])
        loop = AgentLoop(
            llm_backend=llm, tool_registry=tool_registry,
            guardrail_pipeline=GuardrailPipeline(),
            feedback_checkers=passing_feedback, settings=settings,
        )
        state = await loop.run("修改 main.py", "/tmp/project")
        assert state.status == "completed"
        assert state.step_number == 3
        assert len(state.conversation_history) == 3

    async def test_guardrail_blocks_dangerous_command(self, tool_registry, passing_feedback, settings):
        """护栏维度：危险命令被拦截后 Agent 继续安全操作。

        使用 'high' 风险级别（git push --force）而非 'critical'（rm -rf /），
        确保 Agent 被拦截后能继续而非被标记为 blocked 退出。
        """
        guardrails = GuardrailPipeline()
        guardrails.add(PathGuardrail("/tmp/project"))
        guardrails.add(CommandGuardrail())

        llm = MockLLMBackend([
            '{"name": "run_shell", "parameters": {"command": "git push --force origin main"}}',
            '{"name": "run_shell", "parameters": {"command": "pytest"}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = AgentLoop(
            llm_backend=llm, tool_registry=tool_registry,
            guardrail_pipeline=guardrails,
            feedback_checkers=passing_feedback, settings=settings,
        )
        state = await loop.run("测试项目", "/tmp/project")
        assert state.status == "completed"
        assert "BLOCKED:" in state.conversation_history[0]["action_result"]

    async def test_feedback_failure_goes_to_context(self, tool_registry, settings):
        """反馈维度：测试失败信息回灌到 LLM 上下文。"""
        call_count = [0]

        class FailOnceChecker:
            async def check(self, project_path: str) -> FeedbackResult:
                call_count[0] += 1
                if call_count[0] == 1:
                    return FeedbackResult(passed=False, summary="3 tests failed", source="test")
                return FeedbackResult(passed=True, source="test")

        feedback_checker = FailOnceChecker()

        llm = MockLLMBackend([
            '{"name": "write_file", "parameters": {"path": "test.py", "content": "x"}}',
            '{"name": "write_file", "parameters": {"path": "test.py", "content": "fixed"}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = AgentLoop(
            llm_backend=llm, tool_registry=tool_registry,
            guardrail_pipeline=GuardrailPipeline(),
            feedback_checkers=[feedback_checker], settings=settings,
        )
        state = await loop.run("修复测试", "/tmp/project")
        assert state.status == "completed"
        feedback_messages = [
            t for t in state.conversation_history
            if t.get("action_type") == "feedback"
        ]
        assert len(feedback_messages) >= 1

    async def test_tool_not_found_then_corrected(self, tool_registry, passing_feedback, settings):
        """工具维度：调用不存在的工具 → 失败记录 → LLM 修正。"""
        llm = MockLLMBackend([
            '{"name": "delete_file", "parameters": {"path": "x.py"}}',
            '{"name": "read_file", "parameters": {"path": "x.py"}}',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = AgentLoop(
            llm_backend=llm, tool_registry=tool_registry,
            guardrail_pipeline=GuardrailPipeline(),
            feedback_checkers=passing_feedback, settings=settings,
        )
        state = await loop.run("读取文件", "/tmp/project")
        assert state.status == "completed"
        assert "未知工具" in state.conversation_history[0]["action_result"]

    async def test_config_max_steps_enforced(self, tool_registry, passing_feedback):
        """配置维度：max_steps 配置被正确执行。"""
        settings = Settings(max_steps=2)
        llm = MockLLMBackend(['{"name": "read_file", "parameters": {"path": "x.py"}}'] * 5)
        loop = AgentLoop(
            llm_backend=llm, tool_registry=tool_registry,
            guardrail_pipeline=GuardrailPipeline(),
            feedback_checkers=passing_feedback, settings=settings,
        )
        state = await loop.run("任务", "/tmp/project")
        assert state.status == "failed"
        assert state.step_number == 2

    async def test_memory_dimension_session_recording(self, tool_registry, passing_feedback, settings, temp_dir):
        """记忆维度：AgentState 包含完整会话信息，可被 SessionStore 持久化。"""
        from myagent.memory.sqlite import SessionStore

        store = SessionStore(db_path=str(temp_dir / "integration.db"))
        try:
            llm = MockLLMBackend([
                '{"name": "read_file", "parameters": {"path": "a.py"}}',
                '{"name": "DONE", "parameters": {}}',
            ])
            loop = AgentLoop(
                llm_backend=llm, tool_registry=tool_registry,
                guardrail_pipeline=GuardrailPipeline(),
                feedback_checkers=passing_feedback, settings=settings,
            )
            state = await loop.run("test", "/tmp/project")

            assert state.session_id
            assert len(state.conversation_history) == 2
            assert state.status == "completed"

            store.create_session(state.session_id, state.task, state.project_path)
            for i, turn in enumerate(state.conversation_history, 1):
                store.record_turn(
                    session_id=state.session_id, step_number=i,
                    role=turn["role"], content=turn["content"],
                    action_type=turn.get("action_type", ""),
                    action_result=turn.get("action_result", ""),
                )

            turns = store.get_recent_turns(state.session_id, limit=10)
            assert len(turns) == 2
        finally:
            store.close()

    async def test_parser_handles_markdown_json(self, tool_registry, passing_feedback, settings):
        """解析维度：LLM 返回 markdown 包裹的 JSON 也能正确解析。"""
        llm = MockLLMBackend([
            '```json\n{"name": "read_file", "parameters": {"path": "config.py"}}\n```',
            '{"name": "DONE", "parameters": {}}',
        ])
        loop = AgentLoop(
            llm_backend=llm, tool_registry=tool_registry,
            guardrail_pipeline=GuardrailPipeline(),
            feedback_checkers=passing_feedback, settings=settings,
        )
        state = await loop.run("读取配置", "/tmp/project")
        assert state.status == "completed"
        assert state.conversation_history[0]["action_type"] == "read_file"
