"""测试运行反馈 — 调用 pytest 并解析结果。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from myagent.feedback.base import FeedbackError, FeedbackResult


class TestFeedbackRunner:
    """运行 pytest 并解析结果作为反馈信号。"""

    def __init__(self, test_command: str = "python -m pytest -v --tb=short"):
        self._test_command = test_command

    async def check(self, project_path: str) -> FeedbackResult:
        try:
            result = subprocess.run(
                self._test_command.split(),
                cwd=str(Path(project_path).absolute()),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return FeedbackResult(
                passed=False,
                summary="测试运行超时 (120s)",
                source="test",
            )

        passed = result.returncode == 0
        errors = self._parse_errors(result.stdout + result.stderr)

        return FeedbackResult(
            passed=passed,
            errors=errors,
            summary=result.stdout[-500:] if result.stdout else "(无输出)",
            source="test",
        )

    def _parse_errors(self, output: str) -> list[FeedbackError]:
        """从 pytest 输出中提取失败信息。"""
        errors: list[FeedbackError] = []
        # 匹配 pytest 的 FAILED 行
        pattern = r"FAILED\s+([^\s]+)::([^\s]+)"
        for m in re.finditer(pattern, output):
            errors.append(FeedbackError(
                file=m.group(1),
                line=0,
                message=f"测试失败: {m.group(2)}",
                source="test",
            ))
        # 也匹配 AssertionError
        for m in re.finditer(r"E\s+(AssertionError.*)", output):
            errors.append(FeedbackError(
                file="",
                line=0,
                message=m.group(1),
                source="test",
            ))
        return errors

    def _extract_summary(self, output: str) -> str:
        """提取测试摘要。"""
        m = re.search(r"=+ (.*) =+", output)
        if m:
            parts = [p.strip() for p in output.split("=") if p.strip()]
            if parts:
                return parts[-1].strip()
        return output[-200:]
