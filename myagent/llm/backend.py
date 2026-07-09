"""LLM Backend Protocol — 定义 LLM 调用接口。

Agent 通过此接口调用 LLM 决策下一步动作，不依赖具体供应商实现。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    """LLM 决策接口。

    所有 LLM 后端（真实供应商、Mock 测试）必须实现此协议。
    只暴露一个方法：给定上下文和可用工具，返回下一步动作的 JSON 字符串。
    """

    async def decide(self, context: str, tools: list[dict]) -> str:
        """根据上下文和可用工具，决定下一步动作。

        Args:
            context: 包含任务描述、对话历史、项目信息的完整上下文。
            tools: 可用工具的 JSON Schema 列表。

        Returns:
            LLM 决策的原始响应字符串（JSON 格式的动作描述）。
        """
        ...
