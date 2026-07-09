"""HITL 状态机测试。"""

import asyncio

import pytest

from myagent.guardrails.base import Action
from myagent.guardrails.hitl import HITLGate, HITLState


class TestHITLGate:
    async def test_approval(self):
        gate = HITLGate()

        async def mock_confirm(action, risk_level):
            return True

        result = await gate.request_approval(
            Action(name="run_shell", parameters={"command": "rm important.txt"}),
            risk_level="high",
            confirm_fn=mock_confirm,
        )
        assert result.allowed is True
        assert gate.state == HITLState.APPROVED

    async def test_rejection(self):
        gate = HITLGate()

        async def mock_confirm(action, risk_level):
            return False

        result = await gate.request_approval(
            Action(name="run_shell", parameters={"command": "rm important.txt"}),
            risk_level="high",
            confirm_fn=mock_confirm,
        )
        assert result.allowed is False
        assert gate.state == HITLState.REJECTED

    async def test_timeout_auto_reject(self):
        gate = HITLGate(timeout=0.1)

        async def slow_confirm(action, risk_level):
            await asyncio.sleep(1.0)
            return True

        result = await gate.request_approval(
            Action(name="run_shell"),
            risk_level="high",
            confirm_fn=slow_confirm,
        )
        assert result.allowed is False
        assert "超时" in result.reason

    async def test_reset_after_decision(self):
        gate = HITLGate()

        async def mock_confirm(action, risk_level):
            return True

        await gate.request_approval(Action(name="test"), "medium", mock_confirm)
        assert gate.state == HITLState.APPROVED

        gate.reset()
        assert gate.state == HITLState.IDLE

    async def test_is_waiting_during_approval(self):
        gate = HITLGate()
        waiting_detected = False

        async def confirm_with_check(action, risk_level):
            nonlocal waiting_detected
            waiting_detected = gate.is_waiting
            return True

        await gate.request_approval(Action(name="test"), "medium", confirm_with_check)
        assert waiting_detected is True
