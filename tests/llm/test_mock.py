"""Mock LLM Backend 测试 — 确定性响应，不依赖网络。"""

import pytest

from myagent.llm.backend import LLMBackend
from myagent.llm.mock import MockLLMBackend


class TestMockLLMBackend:
    """MockLLMBackend 的核心行为测试。"""

    async def test_returns_preset_responses_in_order(self):
        backend = MockLLMBackend(responses=[
            '{"action": "read_file", "path": "main.py"}',
            '{"action": "write_file", "path": "main.py", "content": "fixed"}',
            "DONE",
        ])

        r1 = await backend.decide("fix the bug", [])
        r2 = await backend.decide("fix the bug", [])
        r3 = await backend.decide("fix the bug", [])

        assert r1 == '{"action": "read_file", "path": "main.py"}'
        assert r2 == '{"action": "write_file", "path": "main.py", "content": "fixed"}'
        assert r3 == "DONE"

    async def test_exhausted_responses_repeats_last(self):
        backend = MockLLMBackend(responses=["DONE"])

        r1 = await backend.decide("task", [])
        r2 = await backend.decide("task", [])
        r3 = await backend.decide("task", [])

        assert r1 == "DONE"
        assert r2 == "DONE"
        assert r3 == "DONE"

    async def test_empty_responses_raises(self):
        with pytest.raises(ValueError, match="responses"):
            MockLLMBackend(responses=[])

    async def test_satisfies_protocol(self):
        """MockLLMBackend 满足 LLMBackend Protocol。"""
        backend = MockLLMBackend(responses=["DONE"])
        assert isinstance(backend, LLMBackend)

    async def test_receives_context_and_tools(self):
        """验证 backend 收到的参数正确。"""
        received_context = []
        received_tools = []

        class RecordingMock(MockLLMBackend):
            async def decide(self, context: str, tools: list[dict]) -> str:
                received_context.append(context)
                received_tools.append(tools)
                return await super().decide(context, tools)

        backend = RecordingMock(responses=["DONE"])
        await backend.decide("fix the bug in main.py", [{"name": "read_file"}])

        assert "fix the bug" in received_context[0]
        assert received_tools[0] == [{"name": "read_file"}]
