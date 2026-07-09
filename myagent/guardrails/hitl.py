"""HITL 状态机 — Human-in-the-Loop 人工审批。"""

from __future__ import annotations

import asyncio
from enum import Enum

from myagent.guardrails.base import Action, GuardResult


class HITLState(Enum):
    IDLE = "idle"
    WAITING = "waiting"
    APPROVED = "approved"
    REJECTED = "rejected"


class HITLGate:
    """HITL 审批门 — 高风险操作暂停等待人工确认。

    用法：
        gate = HITLGate(confirm_fn=rich.prompt.Confirm.ask)
        result = await gate.request_approval(action, risk_level="high")
    """

    def __init__(self, timeout: float = 120.0):
        self._state = HITLState.IDLE
        self._timeout = timeout
        self._event = asyncio.Event()

    async def request_approval(self, action: Action, risk_level: str, confirm_fn) -> GuardResult:
        """请求人工审批。超时自动拒绝。

        Args:
            action: 待审批的动作。
            risk_level: 风险等级（medium/high/critical）。
            confirm_fn: async callable，显示确认提示并返回 bool。

        Returns:
            GuardResult：通过或拒绝。
        """
        self._state = HITLState.WAITING

        try:
            approved = await asyncio.wait_for(
                confirm_fn(action, risk_level),
                timeout=self._timeout,
            )
            if approved:
                self._state = HITLState.APPROVED
                return GuardResult(allowed=True, reason="人工审批通过")
            else:
                self._state = HITLState.REJECTED
                return GuardResult(allowed=False, reason="人工审批拒绝", risk_level=risk_level)
        except TimeoutError:
            self._state = HITLState.REJECTED
            return GuardResult(allowed=False, reason=f"审批超时 ({self._timeout}s)，自动拒绝", risk_level=risk_level)

    def reset(self) -> None:
        """重置状态到 IDLE，准备下一次审批。"""
        self._state = HITLState.IDLE

    @property
    def state(self) -> HITLState:
        return self._state

    @property
    def is_waiting(self) -> bool:
        return self._state == HITLState.WAITING
