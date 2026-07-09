"""停机条件 — 判断 Agent 是否应该停止循环。"""

from __future__ import annotations

from myagent.agent.state import AgentState


def stop_when_max_steps(state: AgentState) -> bool:
    """步数达到上限时停机。"""
    return state.step_number >= state.max_steps


def stop_when_task_completed(state: AgentState) -> bool:
    """任务已完成/失败/被拦截时停机。"""
    return state.status != "running"


def stop_when_consecutive_failures(state: AgentState) -> bool:
    """连续失败次数超限时停机。"""
    return state.consecutive_failures >= state.max_consecutive_failures


def should_stop(state: AgentState) -> bool:
    """组合所有停机条件，任一满足即停机。"""
    return (
        stop_when_max_steps(state)
        or stop_when_task_completed(state)
        or stop_when_consecutive_failures(state)
    )
