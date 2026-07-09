"""Lint 反馈 — 调用 ruff 检查代码质量。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from myagent.feedback.base import FeedbackError, FeedbackResult


class LintCheckerFeedback:
    """运行 ruff 检查代码规范。"""

    async def check(self, project_path: str) -> FeedbackResult:
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=text", "."],
                cwd=str(Path(project_path).absolute()),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            return FeedbackResult(
                passed=True,
                summary="ruff 未安装，跳过 lint 检查",
                source="lint",
            )
        except subprocess.TimeoutExpired:
            return FeedbackResult(
                passed=True,
                summary="lint 检查超时",
                source="lint",
            )

        passed = result.returncode == 0
        errors: list[FeedbackError] = []

        if not passed and result.stdout:
            for line in result.stdout.strip().split("\n")[:20]:
                # ruff output format: file.py:line:col: CODE message
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    errors.append(FeedbackError(
                        file=parts[0],
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        message=f"{parts[2].strip()}: {parts[3].strip()}",
                        source="lint",
                    ))

        return FeedbackResult(
            passed=passed,
            errors=errors,
            summary=result.stdout[:500] if result.stdout else "无 lint 问题",
            source="lint",
        )
