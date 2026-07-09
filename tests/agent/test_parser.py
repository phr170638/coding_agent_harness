"""Action 解析器测试。"""

import pytest

from myagent.agent.parser import ActionParseError, ActionParser


class TestActionParser:
    def test_parse_valid_json(self):
        parser = ActionParser()
        action = parser.parse('{"name": "read_file", "parameters": {"path": "main.py"}}')
        assert action.name == "read_file"
        assert action.parameters == {"path": "main.py"}

    def test_parse_json_with_markdown_block(self):
        parser = ActionParser()
        action = parser.parse(
            '```json\n{"name": "write_file", "parameters": {"path": "out.py", "content": "x=1"}}\n```'
        )
        assert action.name == "write_file"
        assert action.parameters == {"path": "out.py", "content": "x=1"}

    def test_parse_json_with_markdown_no_lang_tag(self):
        parser = ActionParser()
        action = parser.parse(
            '```\n{"name": "run_shell", "parameters": {"command": "echo hi"}}\n```'
        )
        assert action.name == "run_shell"
        assert action.parameters == {"command": "echo hi"}

    def test_parse_done_signal(self):
        parser = ActionParser()
        action = parser.parse(
            '{"name": "DONE", "parameters": {"message": "任务完成"}}'
        )
        assert action.name == "DONE"
        assert action.parameters == {"message": "任务完成"}

    def test_parse_json_with_extra_text(self):
        """JSON 前后有额外文字时也能提取。"""
        parser = ActionParser()
        action = parser.parse(
            '我来读取文件。\n{"name": "read_file", "parameters": {"path": "test.py"}}\n后续可以修改。'
        )
        assert action.name == "read_file"
        assert action.parameters == {"path": "test.py"}

    def test_invalid_json_raises(self):
        parser = ActionParser()
        with pytest.raises(ActionParseError, match="无法解析"):
            parser.parse("不是合法的 JSON")

    def test_missing_name_raises(self):
        parser = ActionParser()
        with pytest.raises(ActionParseError, match="缺少 'name' 字段"):
            parser.parse('{"parameters": {"a": 1}}')

    def test_parameters_defaults_to_dict(self):
        parser = ActionParser()
        action = parser.parse('{"name": "list_files"}')
        assert action.name == "list_files"
        assert action.parameters == {}

    def test_is_done(self):
        parser = ActionParser()
        assert parser.is_done(
            parser.parse('{"name": "DONE", "parameters": {}}')
        )
        assert not parser.is_done(
            parser.parse('{"name": "read_file", "parameters": {}}')
        )
