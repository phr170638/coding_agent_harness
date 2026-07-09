#!/usr/bin/env python3
"""演示：HITL（Human-in-the-Loop）人工审批状态机。

展示在执行高风险操作前如何暂停等待用户确认，
包括批准、拒绝、超时三种路径。
"""

import asyncio

from myagent.guardrails.base import Action
from myagent.guardrails.hitl import HITLGate, HITLState


async def simulate_user_approval():
    """模拟用户批准流程。"""
    print("=" * 60)
    print("HITL 演示 — 场景 1: 用户批准")
    print("=" * 60)
    gate = HITLGate(timeout=5.0)

    async def mock_confirm(action: Action, risk_level: str) -> bool:
        print(f"  操作: {action.parameters.get('command', 'N/A')}")
        print(f"  风险等级: {risk_level}")
        return True  # 用户确认

    action = Action(name="run_shell", parameters={"command": "git push --force origin main"})
    result = await gate.request_approval(action, "high", mock_confirm)
    print(f"  结果: {'批准' if result.allowed else '拒绝'} — {result.reason}")
    assert result.allowed
    print()


async def simulate_user_rejection():
    """模拟用户拒绝流程。"""
    print("=" * 60)
    print("HITL 演示 — 场景 2: 用户拒绝")
    print("=" * 60)
    gate = HITLGate(timeout=5.0)

    async def mock_confirm(action: Action, risk_level: str) -> bool:
        print(f"  操作: {action.parameters.get('command', 'N/A')}")
        print(f"  风险等级: {risk_level}")
        return False  # 用户拒绝

    action = Action(name="run_shell", parameters={"command": "rm -rf ./node_modules"})
    result = await gate.request_approval(action, "medium", mock_confirm)
    print(f"  结果: {'批准' if result.allowed else '拒绝'} — {result.reason}")
    assert not result.allowed
    print()


async def simulate_timeout():
    """模拟超时自动拒绝。"""
    print("=" * 60)
    print("HITL 演示 — 场景 3: 超时自动拒绝")
    print("=" * 60)
    gate = HITLGate(timeout=0.3)

    async def slow_confirm(action: Action, risk_level: str) -> bool:
        await asyncio.sleep(10)  # 超长等待，必然超时
        return True

    action = Action(name="run_shell", parameters={"command": "DROP TABLE users"})
    result = await gate.request_approval(action, "critical", slow_confirm)
    print(f"  操作: {action.parameters.get('command', 'N/A')}")
    print(f"  风险等级: critical")
    print(f"  结果: {'批准' if result.allowed else '拒绝'} — {result.reason}")
    assert not result.allowed
    print()


async def main():
    await simulate_user_approval()
    await simulate_user_rejection()
    await simulate_timeout()

    print("=" * 60)
    print("HITL 状态机: IDLE → WAITING → APPROVED/REJECTED → IDLE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
