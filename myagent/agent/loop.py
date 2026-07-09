"""Agent 主循环 — 协调 LLM、工具、护栏、反馈的核心引擎。"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from myagent.agent.parser import ActionParser
from myagent.agent.state import AgentState
from myagent.agent.stop import should_stop
from myagent.config.settings import Settings
from myagent.llm.backend import LLMBackend
from myagent.llm.prompt import PromptBuilder
from myagent.guardrails.pipeline import GuardrailPipeline
from myagent.feedback.base import FeedbackChecker
from myagent.tools.registry import ToolRegistry


class AgentLoop:
    """Agent 主循环 — 纯代码驱动，LLM 仅做决策。"""

    def __init__(
        self,
        llm_backend: LLMBackend,
        tool_registry: ToolRegistry,
        guardrail_pipeline: GuardrailPipeline,
        feedback_checkers: list[FeedbackChecker],
        settings: Settings,
    ) -> None:
        self._llm = llm_backend
        self._tools = tool_registry
        self._guardrails = guardrail_pipeline
        self._feedback = feedback_checkers
        self._settings = settings
        self._parser = ActionParser()

    async def run(self, task: str, project_path: str) -> AgentState:
        """运行 Agent 主循环直到满足停机条件。"""
        session_id = uuid.uuid4().hex[:12]
        state = AgentState(
            session_id=session_id,
            task=task,
            project_path=project_path,
            max_steps=self._settings.max_steps,
            max_consecutive_failures=self._settings.max_consecutive_failures,
        )

        while not should_stop(state):
            state.increment_step()

            # 1. 构建上下文
            tools_schema = self._tools.list_schemas()
            user_prompt = self._build_context(state, tools_schema)

            # 2. LLM 决策
            step_start = time.time()
            raw_response = await self._llm.decide(user_prompt, tools_schema)
            latency_ms = int((time.time() - step_start) * 1000)

            # 3. 解析 Action
            try:
                action = self._parser.parse(raw_response)
            except Exception:
                state.record_failure()
                state.add_to_history("assistant", raw_response, "", "")
                continue

            # 4. DONE 检查（DONE 信号不经过护栏/工具执行）
            if self._parser.is_done(action):
                state.record_success()
                state.add_to_history("assistant", raw_response, "DONE", "")
                state.mark_completed(action.parameters.get("message", "任务完成"))
                break

            # 5. 护栏检查
            guard_result = self._guardrails.check(action)
            if not guard_result.allowed:
                state.record_failure()
                blocked_msg = f"BLOCKED: {guard_result.reason}"
                state.add_to_history("assistant", raw_response, action.name, blocked_msg)
                if guard_result.risk_level == "critical":
                    state.mark_blocked(guard_result.reason)
                continue

            # 6. 工具查找
            tool = self._tools.get(action.name)
            if tool is None:
                state.record_failure()
                state.add_to_history(
                    "assistant", raw_response, action.name,
                    f"未知工具: {action.name}",
                )
                continue

            # 7. 执行工具
            try:
                result = await tool.execute(**action.parameters)
                result_str = json.dumps(result, ensure_ascii=False, default=str)
            except Exception as exc:
                state.record_failure()
                state.add_to_history(
                    "assistant", raw_response, action.name,
                    f"ERROR: {exc}",
                )
                continue

            # 8. 反馈检查
            feedback_passed = True
            for checker in self._feedback:
                fb = await checker.check(project_path)
                if not fb.passed:
                    feedback_passed = False
                    state.conversation_history.append({
                        "role": "system",
                        "content": fb.to_context(),
                        "action_type": "feedback",
                        "action_result": "",
                    })

            state.record_success()
            state.add_to_history("assistant", raw_response, action.name, result_str)

        # 停机后的状态标记
        if state.status == "running":
            if state.step_number >= state.max_steps:
                state.mark_failed(f"达到最大步数 ({state.max_steps})，任务未完成")
            elif state.consecutive_failures >= state.max_consecutive_failures:
                state.mark_failed(f"连续失败 {state.consecutive_failures} 次，中止执行")

        return state

    def _build_context(self, state: AgentState, tools_schema: list[dict]) -> str:
        """构建发送给 LLM 的完整 prompt。"""
        return PromptBuilder.build_user_prompt(
            task=state.task,
            conversation_history=state.conversation_history,
            tools_schema=tools_schema,
            max_history_turns=self._settings.max_conversation_turns,
        )
