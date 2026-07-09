"""测试运行反馈测试。"""

from myagent.feedback.test_runner import TestFeedbackRunner


class TestTestRunnerFeedback:
    async def test_passing_tests(self, temp_dir):
        (temp_dir / "test_ok.py").write_text("""
def test_pass():
    assert True
""")
        checker = TestFeedbackRunner()
        result = await checker.check(str(temp_dir))
        assert result.passed is True
        assert result.source == "test"

    async def test_failing_tests(self, temp_dir):
        (temp_dir / "test_fail.py").write_text("""
def test_fail():
    assert False, "expected failure"
""")
        checker = TestFeedbackRunner()
        result = await checker.check(str(temp_dir))
        assert result.passed is False
        assert len(result.errors) > 0

    async def test_no_tests(self, temp_dir):
        checker = TestFeedbackRunner()
        result = await checker.check(str(temp_dir))
        # pytest 没有发现测试时返回 exit code 5
        assert result.passed is False  # exit code 5 = no tests collected
