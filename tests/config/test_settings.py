"""配置系统测试 — 默认值、YAML 加载、环境变量覆盖。"""

import os
from pathlib import Path

import pytest
import yaml

from myagent.config.settings import Settings


class TestSettingsDefaults:
    """默认值测试。"""

    def test_default_llm_provider(self):
        settings = Settings()
        assert settings.llm_provider == "aliyun_bailian"

    def test_default_model(self):
        settings = Settings()
        assert settings.llm_model == "qwen-turbo"

    def test_default_max_steps(self):
        settings = Settings()
        assert settings.max_steps == 50

    def test_default_tool_timeout(self):
        settings = Settings()
        assert settings.llm_timeout == 120
        assert settings.tool_timeout == 60

    def test_guardrails_enabled_by_default(self):
        settings = Settings()
        assert settings.guardrail_path is True
        assert settings.guardrail_command is True
        assert settings.guardrail_hitl is True


class TestYAMLLoading:
    """YAML 文件加载测试。"""

    def test_load_from_yaml_file(self, temp_dir):
        config_path = temp_dir / "config.yaml"
        config_path.write_text(yaml.dump({"llm_model": "qwen-plus", "max_steps": 30}))

        settings = Settings(_config_file=config_path)
        assert settings.llm_model == "qwen-plus"
        assert settings.max_steps == 30

    def test_partial_yaml_keeps_defaults(self, temp_dir):
        config_path = temp_dir / "config.yaml"
        config_path.write_text(yaml.dump({"llm_model": "qwen-plus"}))

        settings = Settings(_config_file=config_path)
        assert settings.llm_model == "qwen-plus"
        assert settings.max_steps == 50  # 未指定的保留默认值

    def test_missing_config_file_uses_defaults(self):
        settings = Settings(_config_file=Path("/nonexistent/config.yaml"))
        assert settings.llm_model == "qwen-turbo"


class TestEnvOverride:
    """环境变量覆盖测试。"""

    def test_env_overrides_yaml(self, temp_dir, monkeypatch):
        config_path = temp_dir / "config.yaml"
        config_path.write_text(yaml.dump({"llm_model": "qwen-plus"}))

        monkeypatch.setenv("MYAGENT_LLM_MODEL", "qwen-max")

        settings = Settings(_config_file=config_path)
        assert settings.llm_model == "qwen-max"

    def test_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("MYAGENT_MAX_STEPS", "20")
        settings = Settings()
        assert settings.max_steps == 20


class TestToolConfig:
    """工具配置测试。"""

    def test_tools_default_enabled(self):
        settings = Settings()
        assert settings.tool_shell_enabled is True
        assert settings.tool_file_scope == "project"

    def test_command_blacklist(self):
        settings = Settings()
        assert "rm -rf /" in settings.command_blacklist
        assert "DROP TABLE" in settings.command_blacklist


class TestMemoryConfig:
    """记忆系统配置测试。"""

    def test_memory_defaults(self):
        settings = Settings()
        assert settings.max_conversation_turns == 20
        assert settings.chroma_db_path == ".myagent/chroma"
