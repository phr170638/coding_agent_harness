"""Shell 执行工具 — 在项目目录中运行命令。"""

import subprocess
import time
from pathlib import Path


async def run_shell(command: str, cwd: str = ".", timeout: int = 60) -> dict:
    """执行 shell 命令并返回结果。"""
    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(Path(cwd).absolute()),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:],  # 限制输出长度
            "stderr": result.stderr[-2000:],
            "duration_ms": int((time.monotonic() - start) * 1000),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"命令超时 ({timeout}s)",
            "duration_ms": timeout * 1000,
        }
