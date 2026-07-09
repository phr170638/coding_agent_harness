"""文件 I/O 工具 — 读写项目文件。"""

from pathlib import Path


async def read_file(path: str) -> dict:
    """读取文件内容。"""
    p = Path(path)
    if not p.exists():
        return {"error": f"文件不存在: {path}"}
    try:
        content = p.read_text(encoding="utf-8")
        return {"path": str(p.absolute()), "content": content, "size": len(content)}
    except UnicodeDecodeError:
        return {"error": f"无法以 UTF-8 读取文件（可能是二进制文件）: {path}"}


async def write_file(path: str, content: str) -> dict:
    """写入文件内容（覆盖）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"path": str(p.absolute()), "size": len(content), "written": True}
