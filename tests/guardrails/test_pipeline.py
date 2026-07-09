"""护栏管道测试。"""

from myagent.guardrails.base import Action, GuardResult
from myagent.guardrails.pipeline import GuardrailPipeline


class _FakePass:
    """始终通过的护栏。"""
    def check(self, action: Action) -> GuardResult:
        return GuardResult(allowed=True, reason="pass")


class _FakeBlock:
    """始终拦截的护栏。"""
    def check(self, action: Action) -> GuardResult:
        return GuardResult(allowed=False, reason="blocked", risk_level="high")


class TestGuardrailPipeline:
    def test_empty_pipeline_passes(self):
        pipeline = GuardrailPipeline()
        result = pipeline.check(Action(name="read_file", parameters={}))
        assert result.allowed is True

    def test_all_pass(self):
        pipeline = GuardrailPipeline()
        pipeline.add(_FakePass())
        pipeline.add(_FakePass())
        result = pipeline.check(Action(name="read_file"))
        assert result.allowed is True
        assert "通过" in result.reason

    def test_first_blocks_second_not_executed(self):
        pipeline = GuardrailPipeline()
        pipeline.add(_FakeBlock())
        pipeline.add(_FakePass())
        result = pipeline.check(Action(name="run_shell"))
        assert result.allowed is False
        assert result.reason == "blocked"

    def test_second_blocks(self):
        pipeline = GuardrailPipeline()
        pipeline.add(_FakePass())
        pipeline.add(_FakeBlock())
        result = pipeline.check(Action(name="run_shell"))
        assert result.allowed is False

    def test_pipeline_count(self):
        pipeline = GuardrailPipeline()
        pipeline.add(_FakePass())
        pipeline.add(_FakeBlock())
        assert pipeline.count == 2
