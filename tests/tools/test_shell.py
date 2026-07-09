"""Shell 工具测试。"""

from myagent.tools.shell import run_shell


class TestRunShell:
    async def test_echo(self, temp_dir):
        result = await run_shell("echo hello", cwd=str(temp_dir))
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    async def test_nonexistent_command(self, temp_dir):
        result = await run_shell("nonexistent_command_xyz", cwd=str(temp_dir))
        assert result["exit_code"] != 0

    async def test_timeout(self, temp_dir):
        # 使用 sleep 模拟超时
        result = await run_shell("sleep 30", cwd=str(temp_dir), timeout=1)
        assert result["exit_code"] == -1
        assert "超时" in result["stderr"]

    async def test_stderr_captured(self, temp_dir):
        result = await run_shell('python -c "import sys; sys.stderr.write(\'error msg\')"', cwd=str(temp_dir))
        assert "error msg" in result["stderr"]
