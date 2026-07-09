"""反馈系统基础 — FeedbackResult 数据结构和 Checker 协议。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FeedbackError:
    """单条反馈错误。"""

    file: str = ""
    line: int = 0
    message: str = ""
    source: str = ""  # test / lint / typecheck

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "message": self.message, "source": self.source}


@dataclass
class FeedbackResult:
    """反馈管道检查结果。"""

    passed: bool
    errors: list[FeedbackError] = field(default_factory=list)
    summary: str = ""
    source: str = ""

    def to_context(self) -> str:
        """转换为可回灌到 LLM 上下文的文本。"""
        if self.passed:
            return f"[{self.source}] 通过"
        lines = [f"[{self.source}] 失败 — {len(self.errors)} 个错误:"]
        for err in self.errors:
            lines.append(f"  {err.file}:{err.line}: {err.message}")
        return "\n".join(lines)


class FeedbackChecker(Protocol):
    """反馈检查器协议 — 所有 checker 必须实现。"""

    async def check(self, project_path: str) -> FeedbackResult:
        """运行检查并返回结构化结果。"""
        ...
