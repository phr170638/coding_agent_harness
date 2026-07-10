"""护栏基础 — GuardResult 和 Guardrail 协议。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GuardResult:
    """护栏检查结果。"""

    allowed: bool
    reason: str = ""
    risk_level: str = "low"  # low / medium / high / critical


class Guardrail(Protocol):
    """护栏协议 — 所有护栏必须实现 check 方法。"""

    def check(self, action: Action) -> GuardResult:
        """检查给定动作是否允许执行。

        Args:
            action: 待检查的动作。

        Returns:
            GuardResult：allowed=True 放行，allowed=False 拦截。
        """
        ...


@dataclass
class Action:
    """Agent 动作 — LLM 决策的结构化表示。"""

    name: str  # 工具名称
    parameters: dict = field(default_factory=dict)  # 工具参数
