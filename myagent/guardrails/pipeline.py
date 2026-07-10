"""护栏管道 — 链式执行多个护栏。"""

from myagent.guardrails.base import Action, Guardrail, GuardResult


class GuardrailPipeline:
    """串行执行一组护栏，任一拦截即停止后续检查。"""

    def __init__(self) -> None:
        self._guardrails: list[Guardrail] = []

    def add(self, guardrail: Guardrail) -> None:
        """添加一个护栏到管道末尾。"""
        self._guardrails.append(guardrail)

    def check(self, action: Action) -> GuardResult:
        """按序执行所有护栏，返回第一个拦截结果。

        Returns:
            如果所有护栏通过，返回 allowed=True。
            如果任一护栏拦截，返回该护栏的 GuardResult。
        """
        for guardrail in self._guardrails:
            result = guardrail.check(action)
            if not result.allowed:
                return result
        return GuardResult(allowed=True, reason="所有护栏检查通过")

    @property
    def count(self) -> int:
        return len(self._guardrails)
