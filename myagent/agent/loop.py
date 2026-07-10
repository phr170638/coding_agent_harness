"""Agent 主循环 — 协调 LLM、工具、护栏、反馈的核心引擎。"""

from __future__ import annotations

import json
import time
import uuid

from myagent.agent.parser import ActionParser
from myagent.agent.state import AgentState
from myagent.agent.stop import should_stop
from myagent.config.settings import Settings
from myagent.feedback.base import FeedbackChecker
from myagent.guardrails.pipeline import GuardrailPipeline
from myagent.llm.backend import LLMBackend
from myagent.llm.prompt import PromptBuilder
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
        on_event: callable = None,
    ) -> None:
        self._llm = llm_backend
        self._tools = tool_registry
        self._guardrails = guardrail_pipeline
        self._feedback = feedback_checkers
        self._settings = settings
        self._parser = ActionParser()
        self._on_event = on_event  # async callable: on_event(event: dict) -> None

    async def _emit(self, event_type: str, **kwargs) -> None:
        """发送事件到回调（若注册）。"""
        if self._on_event:
            event = {"type": event_type, **kwargs}
            await self._on_event(event)

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
            await self._emit("thinking", step=state.step_number)
            step_start = time.time()
            raw_response = await self._llm.decide(user_prompt, tools_schema)
            latency_ms = int((time.time() - step_start) * 1000)
            await self._emit("llm_response", step=state.step_number, content=raw_response[:500], latency_ms=latency_ms)

            # 3. 解析 Action
            try:
                action = self._parser.parse(raw_response)
            except Exception as exc:
                await self._emit("parse_error", step=state.step_number, error=str(exc))
                state.record_failure()
                state.add_to_history("assistant", raw_response, "", "")
                continue

            # 4. DONE 检查
            if self._parser.is_done(action):
                msg = action.parameters.get("message", "任务完成")
                await self._emit("done", step=state.step_number, message=msg)
                state.record_success()
                state.add_to_history("assistant", raw_response, "DONE", "")
                state.mark_completed(msg)
                break

            await self._emit("action", step=state.step_number, name=action.name, parameters=action.parameters)

            # 5. 护栏检查
            guard_result = self._guardrails.check(action)
            await self._emit(
                "guardrail", step=state.step_number,
                allowed=guard_result.allowed, reason=guard_result.reason,
                risk_level=guard_result.risk_level,
            )
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
                await self._emit("tool_error", step=state.step_number, error=f"未知工具: {action.name}")
                state.record_failure()
                state.add_to_history("assistant", raw_response, action.name, f"未知工具: {action.name}")
                continue

            # 7. 执行工具
            try:
                result = await tool.execute(**action.parameters)
                result_str = json.dumps(result, ensure_ascii=False, default=str)
                await self._emit("tool_result", step=state.step_number, name=action.name, result=result_str[:500])
            except Exception as exc:
                await self._emit("tool_error", step=state.step_number, error=str(exc))
                state.record_failure()
                state.add_to_history("assistant", raw_response, action.name, f"ERROR: {exc}")
                continue

            # 8. 反馈检查
            for checker in self._feedback:
                fb = await checker.check(project_path)
                await self._emit(
                    "feedback", step=state.step_number,
                    passed=fb.passed, summary=fb.summary[:200], source=fb.source,
                )
                if not fb.passed:
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

        await self._emit("finished", status=state.status, steps=state.step_number, message=state.completion_message)
        return state

    def _build_context(self, state: AgentState, tools_schema: list[dict]) -> str:
        """构建发送给 LLM 的完整 prompt。"""
        return PromptBuilder.build_user_prompt(
            task=state.task,
            conversation_history=state.conversation_history,
            tools_schema=tools_schema,
            max_history_turns=self._settings.max_conversation_turns,
        )
