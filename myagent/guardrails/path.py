"""路径护栏 — 限制文件操作在项目目录内。"""

from pathlib import Path

from myagent.guardrails.base import Action, GuardResult


class PathGuardrail:
    """检查文件路径是否在项目根目录范围内。"""

    def __init__(self, project_root: str | Path) -> None:
        self._project_root = Path(project_root).resolve()

    def check(self, action: Action) -> GuardResult:
        # 只检查涉及文件路径的操作
        path_value = action.parameters.get("path") or action.parameters.get("filepath")
        if not path_value:
            return GuardResult(allowed=True, reason="非文件操作")

        target = Path(path_value)
        # 相对路径相对于项目根解析
        if not target.is_absolute():
            target = (self._project_root / target).resolve()
        else:
            target = target.resolve()

        # 检查路径是否在项目根内
        try:
            target.relative_to(self._project_root)
            return GuardResult(allowed=True, reason="路径在项目范围内")
        except ValueError:
            return GuardResult(
                allowed=False,
                reason=f"路径越界：'{path_value}' 不在项目目录 '{self._project_root}' 内",
                risk_level="high",
            )
