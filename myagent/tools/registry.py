"""工具注册中心 — 管理已注册工具的查找和 schema 导出。"""

from myagent.tools.base import Tool


class ToolRegistry:
    """工具注册中心。

    注册所有可用工具，提供按名称查找和 schema 列表导出功能。
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具，同名重复注册抛出异常。"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """按名称获取工具，不存在时返回 None。"""
        return self._tools.get(name)

    def list_schemas(self) -> list[dict]:
        """导出所有工具的 OpenAI function calling schema 列表。"""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def list_names(self) -> list[str]:
        """列出所有已注册的工具名称。"""
        return list(self._tools.keys())
