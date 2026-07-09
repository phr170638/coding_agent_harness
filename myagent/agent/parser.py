"""Action 解析器 — 将 LLM 输出解析为结构化的 Action 对象。"""

from __future__ import annotations

import json
import re

from myagent.guardrails.base import Action


class ActionParseError(Exception):
    """Action 解析失败。"""


class ActionParser:
    """解析 LLM 输出的 JSON，支持多种格式。"""

    done_marker = "DONE"

    def parse(self, raw_output: str) -> Action:
        """从 LLM 原始输出中提取并解析 Action JSON。

        支持格式：
        - 纯 JSON: {"name": "tool", "parameters": {...}}
        - markdown 代码块包裹的 JSON
        - 文本中嵌入的 JSON 对象
        """
        json_str = self._extract_json(raw_output)
        if not json_str:
            raise ActionParseError(f"无法解析 LLM 输出中的 JSON: {raw_output[:200]}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ActionParseError(f"JSON 解析失败: {e}") from e

        name = data.get("name", "")
        if not name:
            raise ActionParseError("Action JSON 缺少 'name' 字段")

        return Action(name=name, parameters=data.get("parameters", {}))

    def is_done(self, action: Action) -> bool:
        """判断是否为终止信号。"""
        return action.name.upper() == self.done_marker

    def _extract_json(self, text: str) -> str | None:
        """从文本中提取 JSON 字符串。"""
        # 1. 尝试匹配 markdown 代码块中的 JSON
        md_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        m = re.search(md_pattern, text)
        if m:
            return m.group(1).strip()

        # 2. 尝试找到第一个 JSON 对象 {...}
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text)
        for candidate in reversed(matches):  # 取最后一个（最可能是 action）
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

        return None
