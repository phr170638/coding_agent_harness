"""代码搜索工具 — 在项目中搜索文本模式。"""

from __future__ import annotations

import subprocess
from pathlib import Path


async def search_code(pattern: str, cwd: str = ".") -> dict:
    """在项目文件中搜索模式匹配。优先使用 ripgrep，fallback 到 Python 实现。"""
    project_dir = str(Path(cwd).absolute())

    # 尝试使用 rg
    try:
        result = subprocess.run(
            ["rg", "--line-number", "--max-count=20", pattern, project_dir],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[:20]
            return {"matches": lines, "count": len(lines), "tool": "rg"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: Python 实现
    matches = []
    project_path = Path(project_dir)
    for f in project_path.rglob("*.py"):
        if ".venv" in str(f) or "__pycache__" in str(f):
            continue
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines()):
                if pattern in line:
                    matches.append(f"{f.relative_to(project_path)}:{i + 1}: {line.strip()}")
                    if len(matches) >= 20:
                        break
        except (OSError, UnicodeDecodeError):
            continue
        if len(matches) >= 20:
            break

    return {"matches": matches, "count": len(matches), "tool": "python"}
