"""工具注册中心测试。"""

import pytest

from myagent.tools.base import Tool
from myagent.tools.registry import ToolRegistry


async def _dummy_execute(**kwargs):
    return {"result": "ok"}


class TestToolRegistry:
    """ToolRegistry 的核心行为测试。"""

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = Tool(
            name="read_file",
            description="读取文件",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            execute=_dummy_execute,
        )
        registry.register(tool)
        assert registry.get("read_file") is tool

    def test_get_nonexistent_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_register_duplicate_raises(self):
        registry = ToolRegistry()
        tool = Tool(name="test", description="test tool", parameters={}, execute=_dummy_execute)
        registry.register(tool)
        with pytest.raises(ValueError, match="已注册"):
            registry.register(tool)

    def test_list_all_schemas(self):
        registry = ToolRegistry()
        registry.register(Tool(
            name="read_file", description="读取文件",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            execute=_dummy_execute,
        ))
        registry.register(Tool(
            name="write_file", description="写入文件",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            execute=_dummy_execute,
        ))
        schemas = registry.list_schemas()
        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert "read_file" in names
        assert "write_file" in names

    def test_list_names(self):
        registry = ToolRegistry()
        registry.register(Tool(
            name="read_file", description="读取文件",
            parameters={}, execute=_dummy_execute,
        ))
        assert "read_file" in registry.list_names()
