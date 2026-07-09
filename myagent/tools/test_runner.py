"""测试运行工具 — 调用 pytest 并解析结果。"""

from __future__ import annotations

import subprocess
from pathlib import Path


async def run_tests(cwd: str = ".", test_path: str = "") -> dict:
    """运行项目测试并返回结构化结果。"""
    cmd = ["python", "-m", "pytest", "-v", "--tb=short"]
    if test_path:
        cmd.append(test_path)

    result = subprocess.run(
        cmd,
        cwd=str(Path(cwd).absolute()),
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-1000:],
    }
