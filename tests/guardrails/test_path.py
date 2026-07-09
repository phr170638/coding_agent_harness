"""路径护栏测试。"""

from pathlib import Path

from myagent.guardrails.base import Action
from myagent.guardrails.path import PathGuardrail


class TestPathGuardrail:
    def test_project_path_allowed(self, temp_dir):
        guard = PathGuardrail(temp_dir)
        test_file = temp_dir / "main.py"
        action = Action(name="read_file", parameters={"path": str(test_file)})
        result = guard.check(action)
        assert result.allowed is True

    def test_parent_escape_blocked(self, temp_dir):
        guard = PathGuardrail(temp_dir)
        action = Action(name="read_file", parameters={"path": str(temp_dir / ".." / ".." / "etc" / "passwd")})
        result = guard.check(action)
        assert result.allowed is False
        assert "越界" in result.reason

    def test_absolute_path_outside_blocked(self, temp_dir):
        guard = PathGuardrail(temp_dir)
        action = Action(name="read_file", parameters={"path": "/etc/passwd"})
        result = guard.check(action)
        assert result.allowed is False

    def test_non_file_action_passes(self, temp_dir):
        guard = PathGuardrail(temp_dir)
        action = Action(name="run_shell", parameters={"command": "echo hello"})
        result = guard.check(action)
        assert result.allowed is True

    def test_relative_path_allowed(self, temp_dir):
        guard = PathGuardrail(temp_dir)
        action = Action(name="write_file", parameters={"path": "src/new_file.py"})
        result = guard.check(action)
        assert result.allowed is True
