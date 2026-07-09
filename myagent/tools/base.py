"""工具基类 — 定义 Tool 数据结构和执行协议。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    """可在 Agent 循环中调用的工具。"""

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[dict[str, Any]]]

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式的 schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
