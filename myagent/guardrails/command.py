"""命令护栏 — 拦截危险 shell 命令。"""

import re

from myagent.guardrails.base import Action, GuardResult

# 危险命令模式（正则黑名单）
_DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, risk_level, description)
    (r"rm\s+-rf\s+/", "critical", "递归强制删除根目录"),
    (r"rm\s+-rf\s+\/\*", "critical", "递归强制删除根目录"),
    (r"rm\s+-rf\s+~", "high", "递归强制删除用户目录"),
    (r"DROP\s+TABLE", "critical", "删除数据库表"),
    (r"DROP\s+DATABASE", "critical", "删除数据库"),
    (r"DELETE\s+FROM", "high", "数据库批量删除"),
    (r"chmod\s+777\s+/", "high", "危险权限修改"),
    (r"mkfs\.", "critical", "格式化文件系统"),
    (r"dd\s+if=", "critical", "磁盘直接写入"),
    (r">\s*/dev/sd", "critical", "写入磁盘设备"),
    (r"curl.*\|.*(ba)?sh", "critical", "curl pipe shell 执行"),
    (r"wget.*\|.*(ba)?sh", "critical", "wget pipe shell 执行"),
    (r"git\s+push\s+--force.*main", "high", "强制推送到 main 分支"),
    (r"git\s+push\s+--force.*master", "high", "强制推送到 master 分支"),
    (r"sudo\s+su", "high", "提权"),
    (r"ssh\s+root@", "high", "SSH 到 root"),
]


class CommandGuardrail:
    """检查 shell 命令是否危险。

    采用双层防护：
    L1: 正则黑名单匹配
    L2: 白名单验证（如果配置了允许列表）
    """

    def __init__(self, blacklist: list[str] | None = None, whitelist: list[str] | None = None):
        self._extra_blacklist = blacklist or []
        self._whitelist = whitelist or []

    def check(self, action: Action) -> GuardResult:
        if action.name != "run_shell":
            return GuardResult(allowed=True, reason="非 shell 命令")

        command = action.parameters.get("command", "")
        if not command:
            return GuardResult(allowed=True, reason="空命令")

        # L2: 白名单优先
        if self._whitelist:
            for allowed in self._whitelist:
                if re.match(allowed, command):
                    return GuardResult(allowed=True, reason=f"命中白名单: {allowed}")
            return GuardResult(
                allowed=False,
                reason=f"命令不在白名单中: {command[:80]}",
                risk_level="medium",
            )

        # L1: 黑名单匹配
        for pattern, risk_level, description in _DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return GuardResult(
                    allowed=False,
                    reason=f"危险命令已拦截: {description} (匹配: {pattern})",
                    risk_level=risk_level,
                )

        # 额外自定义黑名单
        for pattern in self._extra_blacklist:
            if re.search(pattern, command, re.IGNORECASE):
                return GuardResult(
                    allowed=False,
                    reason=f"命中自定义黑名单: {pattern}",
                    risk_level="high",
                )

        return GuardResult(allowed=True, reason="命令安全检查通过")
