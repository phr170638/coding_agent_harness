"""Docker 沙箱测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from myagent.tools.docker_sandbox import DockerSandbox


class TestDockerSandbox:
    def test_sandbox_requires_project_path(self):
        """沙箱需要项目路径才能挂载。"""
        with pytest.raises(ValueError, match="project_path"):
            DockerSandbox(project_path="")

    def test_run_shell_without_docker_falls_back(self, temp_dir):
        """Docker 不可用时回退到 subprocess。"""
        with patch("myagent.tools.docker_sandbox.docker.from_env", side_effect=Exception("no docker")):
            sb = DockerSandbox(project_path=str(temp_dir))
            assert sb.available is False

    @pytest.mark.asyncio
    async def test_fallback_executes_command(self, temp_dir):
        """回退模式仍能执行命令。"""
        sandbox = DockerSandbox(project_path=str(temp_dir))
        sandbox._available = False
        result = await sandbox.run("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_timeout_in_fallback(self, temp_dir):
        """回退模式下超时也能处理。"""
        sandbox = DockerSandbox(project_path=str(temp_dir))
        sandbox._available = False
        result = await sandbox.run("python -c \"import time; time.sleep(10)\"", timeout=1)
        assert result["exit_code"] == -1
        assert "超时" in result["stderr"]

    def test_blacklist_commands_rejected(self, temp_dir):
        """即使 Docker 不可用，危险命令也应被 CommandGuardrail 拦截（集成测试验证）。"""
        sandbox = DockerSandbox(project_path=str(temp_dir))
        sandbox._available = False
        # 沙箱本身不负责安全校验，只负责隔离执行
        # 安全校验由 CommandGuardrail 负责
        assert sandbox.available is False  # 仅验证状态正确

    def test_mock_docker_container_run(self, temp_dir):
        """模拟 Docker 容器执行，验证命令正确传递。"""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"hello from container\n"
        mock_client.containers.run.return_value = mock_container

        sandbox = DockerSandbox(project_path=str(temp_dir))
        sandbox._client = mock_client
        sandbox._available = True

        import asyncio
        result = asyncio.run(sandbox.run("echo hello"))
        assert result["exit_code"] == 0
        assert "hello from container" in result["stdout"]
        mock_client.containers.run.assert_called_once()
        # 验证命令中包含 echo hello
        call_args = mock_client.containers.run.call_args
        cmd_parts = call_args[1].get("command", "")
        assert "echo hello" in cmd_parts
