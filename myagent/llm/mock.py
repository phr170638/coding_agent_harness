"""Mock LLM Backend — 确定性响应，用于单元测试。

不依赖网络和真实 LLM，预设的响应序列确保每次测试结果一致。
"""

from myagent.llm.backend import LLMBackend


class MockLLMBackend:
    """返回预设响应序列的 LLM 后端，用于测试 agent 核心机制。

    每次调用 decide() 按序返回预设响应。响应耗尽后重复最后一条。
    """

    def __init__(self, responses: list[str]) -> None:
        if not responses:
            raise ValueError("responses 不能为空，至少需要一个预设响应")
        self._responses = responses
        self._index = 0
        self._call_count = 0

    async def decide(self, context: str, tools: list[dict]) -> str:
        self._call_count += 1
        if self._index < len(self._responses):
            response = self._responses[self._index]
            self._index += 1
            return response
        return self._responses[-1]
