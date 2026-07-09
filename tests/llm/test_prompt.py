"""Prompt 构建器测试 — 系统提示、用户提示、token 截断。"""

from myagent.llm.prompt import PromptBuilder


class TestPromptBuilder:
    """PromptBuilder 的核心行为测试。"""

    def test_build_system_prompt(self):
        prompt = PromptBuilder.build_system_prompt()
        assert "编码助手" in prompt
        assert "JSON" in prompt
        assert "DONE" in prompt

    def test_build_user_prompt_basic(self):
        prompt = PromptBuilder.build_user_prompt(
            task="在 main.py 中实现 hello 函数",
        )
        assert "main.py" in prompt
        assert "hello" in prompt

    def test_build_user_prompt_with_project_files(self):
        prompt = PromptBuilder.build_user_prompt(
            task="修复 bug",
            project_files={"main.py": "print('hello')", "utils.py": "def add(a,b): return a+b"},
        )
        assert "main.py" in prompt
        assert "utils.py" in prompt
        assert "print('hello')" in prompt

    def test_build_user_prompt_with_history(self):
        prompt = PromptBuilder.build_user_prompt(
            task="继续修复",
            conversation_history=[
                {"role": "assistant", "content": "读取了 main.py"},
                {"role": "tool", "content": "文件内容..."},
            ],
        )
        assert "main.py" in prompt
        assert "读取了" in prompt

    def test_build_user_prompt_includes_tools_section(self):
        prompt = PromptBuilder.build_user_prompt(
            task="完成任务",
        )
        assert "可用工具" in prompt

    def test_truncate_long_history(self):
        """长对话历史应被截断，保留最近 N 轮。"""
        long_history = [
            {"role": "assistant", "content": f"step {i}: did something"} for i in range(50)
        ]
        prompt = PromptBuilder.build_user_prompt(
            task="final task",
            conversation_history=long_history,
            max_history_turns=10,
        )
        # 最近 10 轮应保留
        assert "step 40:" in prompt or "step 49:" in prompt
        # 最早的不应存在
        assert "step 0:" not in prompt

    def test_empty_context_fields_handled(self):
        prompt = PromptBuilder.build_user_prompt(task="simple task")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
