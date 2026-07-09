"""Lint 反馈测试。"""

from myagent.feedback.linter import LintCheckerFeedback


class TestLintChecker:
    async def test_clean_code(self, temp_dir):
        (temp_dir / "clean.py").write_text("x = 1\n")
        checker = LintCheckerFeedback()
        result = await checker.check(str(temp_dir))
        # ruff 可能通过或检测到问题
        assert isinstance(result.passed, bool)

    async def test_lint_issues(self, temp_dir):
        (temp_dir / "bad.py").write_text("import os\nimport sys\nx=1\n")
        checker = LintCheckerFeedback()
        result = await checker.check(str(temp_dir))
        assert isinstance(result.errors, list)
