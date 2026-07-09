"""配置系统 — 基于 Pydantic Settings，支持 YAML 文件 + 环境变量覆盖。"""

import os
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent 全局配置，加载优先级：显式 kwarg > 环境变量 > YAML 文件 > 默认值。"""

    model_config = SettingsConfigDict(
        env_prefix="MYAGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "aliyun_bailian"
    llm_model: str = "qwen-turbo"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_timeout: int = 120

    # Embedding
    embedding_model: str = "text-embedding-v3"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Agent
    max_steps: int = 50
    tool_timeout: int = 60

    # Tools
    tool_shell_enabled: bool = True
    tool_shell_sandbox: str = "docker"  # docker | none
    tool_file_scope: str = "project"  # project | global

    # Guardrails
    guardrail_path: bool = True
    guardrail_command: bool = True
    guardrail_network: bool = True
    guardrail_hitl: bool = True
    command_blacklist: list[str] = [
        "rm -rf /",
        "DROP TABLE",
        "DELETE FROM",
        r"curl.*\|.*sh",
        "chmod 777 /",
        "mkfs",
        "dd if=",
        "> /dev/sda",
    ]
    command_whitelist: list[str] = []

    # Feedback
    feedback_run_tests: bool = True
    feedback_run_lint: bool = True
    feedback_run_typecheck: bool = False

    # Memory
    max_conversation_turns: int = 20
    chroma_db_path: str = ".myagent/chroma"
    sqlite_db_path: str = ".myagent/sessions.db"

    def __init__(self, **kwargs):
        _config_file: Path | None = kwargs.pop("_config_file", None)  # type: ignore[assignment]

        # 1. 加载 YAML 文件
        yaml_data: dict = {}
        config_path = _config_file or Path(".myagent/config.yaml")
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}

        # 2. 环境变量优先于 YAML：从 YAML 中移除已被环境变量覆盖的 key
        for key in list(yaml_data.keys()):
            env_key = f"MYAGENT_{key.upper()}"
            if env_key in os.environ:
                del yaml_data[key]

        # 3. YAML 值作为默认值，环境变量 + 显式 kwarg 可覆盖
        super().__init__(**yaml_data, **kwargs)
