"""Agent 状态 — 追踪运行中的 Agent 状态。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AgentState:
    """Agent 运行状态，贯穿整个主循环。"""

    session_id: str
    task: str
    project_path: str
    max_steps: int = 50
    max_consecutive_failures: int = 3
    step_number: int = 0
    status: str = "running"  # running | completed | failed | blocked
    completion_message: str = ""
    consecutive_failures: int = 0
    conversation_history: list[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def increment_step(self) -> None:
        self.step_number += 1

    def add_to_history(
        self,
        role: str,
        content: str,
        action_type: str = "",
        action_result: str = "",
    ) -> None:
        self.conversation_history.append(
            {
                "role": role,
                "content": content,
                "action_type": action_type,
                "action_result": action_result,
            }
        )

    def record_failure(self) -> None:
        self.consecutive_failures += 1

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def mark_completed(self, message: str = "") -> None:
        self.status = "completed"
        self.completion_message = message

    def mark_failed(self, message: str = "") -> None:
        self.status = "failed"
        self.completion_message = message

    def mark_blocked(self, message: str = "") -> None:
        self.status = "blocked"
        self.completion_message = message
