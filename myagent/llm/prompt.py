"""Prompt 构建器 — 组装发送给 LLM 的完整上下文。"""

from __future__ import annotations

SYSTEM_PROMPT = """你是一个编码助手 Agent。你需要根据当前上下文决定下一步操作。

你的输出必须是严格的 JSON 格式：
{"name": "<工具名称>", "parameters": {<参数>}}

当任务已完成时，输出：
{"name": "DONE", "parameters": {"message": "<完成总结>"}}

规则：
1. 每次只执行一个工具调用
2. 在写代码前先读取相关文件
3. 修改后运行测试验证
4. 如果测试失败，根据错误信息修正代码
5. 不要猜测文件内容，不确定时就读取"""


class PromptBuilder:
    """构建发送给 LLM 的结构化 prompt。"""

    @staticmethod
    def build_system_prompt() -> str:
        return SYSTEM_PROMPT

    @staticmethod
    def build_user_prompt(
        task: str,
        project_files: dict[str, str] | None = None,
        conversation_history: list[dict] | None = None,
        tools_schema: list[dict] | None = None,
        max_history_turns: int = 20,
    ) -> str:
        sections: list[str] = []

        # 任务
        sections.append("## 任务")
        sections.append(task)
        sections.append("")

        # 项目文件
        if project_files:
            sections.append("## 项目文件")
            for filepath, content in project_files.items():
                sections.append(f"### {filepath}")
                sections.append("```")
                sections.append(content[:3000])
                sections.append("```")
                sections.append("")

        # 对话历史（截断到最近 N 轮）
        if conversation_history:
            truncated = conversation_history[-max_history_turns * 2:]
            sections.append("## 对话历史")
            for entry in truncated:
                role = entry.get("role", "unknown")
                content = entry.get("content", "")
                sections.append(f"**{role}**: {content[:500]}")
                sections.append("")
            if len(conversation_history) > max_history_turns * 2:
                sections.append(f"(已截断 {len(conversation_history) - max_history_turns * 2} 条历史记录)")

        # 可用工具
        if tools_schema:
            sections.append("## 可用工具")
            for tool in tools_schema:
                sections.append(f"- **{tool['function']['name']}**: {tool['function']['description']}")
            sections.append("")

        return "\n".join(sections)
