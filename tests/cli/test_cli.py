"""CLI 测试 — 用 Typer CliRunner 验证命令。"""

from unittest.mock import AsyncMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from myagent.cli.main import app

runner = CliRunner()


class TestInitCommand:
    def test_init_creates_config_file(self, temp_dir):
        config_path = temp_dir / ".myagent" / "config.yaml"
        result = runner.invoke(app, ["init", "--path", str(temp_dir)])
        assert result.exit_code == 0
        assert config_path.exists()

    def test_init_config_content(self, temp_dir):
        result = runner.invoke(app, ["init", "--path", str(temp_dir)])
        assert result.exit_code == 0
        config = yaml.safe_load((temp_dir / ".myagent" / "config.yaml").read_text(encoding="utf-8"))
        assert config["llm_provider"] == "aliyun_bailian"
        assert config["max_steps"] == 50

    def test_init_skips_if_exists(self, temp_dir):
        """配置已存在时不覆盖。"""
        config_dir = temp_dir / ".myagent"
        config_dir.mkdir()
        config_dir.joinpath("config.yaml").write_text("custom: true", encoding="utf-8")

        result = runner.invoke(app, ["init", "--path", str(temp_dir)])
        assert "已存在" in result.output or "已存在" in result.stdout


class TestKeyCommand:
    def test_key_status_shows_not_set(self, temp_dir):
        with patch("myagent.cli.key.CredentialStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.exists.return_value = False
            result = runner.invoke(app, ["key", "status"])
            assert "未配置" in result.output or "not set" in result.output.lower()

    def test_key_status_shows_configured(self, temp_dir):
        with patch("myagent.cli.key.CredentialStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            mock_store.exists.return_value = True
            result = runner.invoke(app, ["key", "status"])
            assert "已配置" in result.output

    def test_key_clear(self, temp_dir):
        with patch("myagent.cli.key.CredentialStore") as mock_store_cls:
            mock_store = mock_store_cls.return_value
            result = runner.invoke(app, ["key", "clear"], input="y\n")
            assert result.exit_code == 0
            mock_store.delete.assert_called()


class TestRunCommand:
    def test_run_requires_task(self, temp_dir):
        result = runner.invoke(app, ["run"])
        # 需要提供 task 参数
        assert result.exit_code != 0

    def test_run_with_mock_llm(self, temp_dir):
        """用 mock 响应运行简化循环，验证基本流程。"""
        with patch("myagent.cli.run.AgentLoop") as mock_loop_cls:
            mock_loop = mock_loop_cls.return_value
            mock_state = AsyncMock()
            mock_state.status = "completed"
            mock_state.step_number = 3
            mock_state.conversation_history = [
                {"role": "assistant", "action_type": "write_file", "action_result": '{"ok": true}'},
                {"role": "assistant", "action_type": "DONE", "action_result": ""},
            ]
            mock_loop.run = AsyncMock(return_value=mock_state)

            result = runner.invoke(app, ["run", "--mock", "--project", str(temp_dir), "实现 hello world"])
            assert result.exit_code == 0
