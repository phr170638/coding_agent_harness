"""CLI 入口 — Typer 应用定义。"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

app = typer.Typer(name="myagent", help="Coding Agent Harness — LLM 驱动的编码助手")

# 注册子命令
from myagent.cli.key import app as key_app  # noqa: E402
from myagent.cli.run import run_task  # noqa: E402

app.add_typer(key_app, name="key", help="管理 API 凭据")
app.command(name="run")(run_task)


@app.command()
def init(
    path: str = typer.Option(".", "--path", "-p", help="项目路径"),
    force: bool = typer.Option(False, "--force", "-f", help="强制覆盖已有配置"),
):
    """在当前项目生成 .myagent/config.yaml 配置文件。"""
    config_dir = Path(path).resolve() / ".myagent"
    config_file = config_dir / "config.yaml"

    if config_file.exists() and not force:
        typer.echo(f"配置文件已存在: {config_file}")
        typer.echo("使用 --force 强制覆盖")
        return

    config_dir.mkdir(parents=True, exist_ok=True)

    defaults = {
        "llm_provider": "aliyun_bailian",
        "llm_model": "qwen-turbo",
        "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "llm_timeout": 120,
        "embedding_model": "text-embedding-v3",
        "max_steps": 50,
        "max_consecutive_failures": 3,
        "tool_timeout": 60,
        "tool_shell_enabled": True,
        "tool_shell_sandbox": "docker",
        "tool_file_scope": "project",
        "guardrail_path": True,
        "guardrail_command": True,
        "guardrail_network": True,
        "guardrail_hitl": True,
        "command_blacklist": [
            "rm -rf /",
            "DROP TABLE",
            "DELETE FROM",
        ],
        "command_whitelist": [],
        "feedback_run_tests": True,
        "feedback_run_lint": True,
        "feedback_run_typecheck": False,
        "max_conversation_turns": 20,
        "chroma_db_path": ".myagent/chroma",
        "sqlite_db_path": ".myagent/sessions.db",
    }

    config_file.write_text(yaml.dump(defaults, allow_unicode=True, default_flow_style=False), encoding="utf-8")
    typer.echo(f"✓ 已生成配置文件: {config_file}")


if __name__ == "__main__":
    app()
