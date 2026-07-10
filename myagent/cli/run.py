"""run 子命令 — 启动 Agent 主循环。"""

from __future__ import annotations

from pathlib import Path

import typer

from myagent.agent.loop import AgentLoop
from myagent.config.settings import Settings
from myagent.guardrails.command import CommandGuardrail
from myagent.guardrails.pipeline import GuardrailPipeline
from myagent.guardrails.path import PathGuardrail
from myagent.llm.bailian import AliBailianBackend
from myagent.tools.file_io import read_file, write_file
from myagent.tools.registry import ToolRegistry
from myagent.tools.shell import run_shell


def run_task(
    task: str = typer.Argument(..., help="任务描述"),
    project: str = typer.Option(".", "--project", "-p", help="项目路径"),
    config: str = typer.Option("", "--config", "-c", help="配置文件路径"),
    max_steps: int = typer.Option(0, "--max-steps", help="最大步数（覆盖配置）"),
    mock: bool = typer.Option(False, "--mock", help="使用 Mock LLM（仅用于调试）"),
):
    """运行 Agent 完成指定任务。"""
    settings = Settings(_config_file=Path(config or ".myagent/config.yaml"))
    if max_steps > 0:
        settings.max_steps = max_steps

    project_path = str(Path(project).resolve())

    # 构建后端
    if mock:
        from myagent.llm.mock import MockLLMBackend
        llm = MockLLMBackend([
            '{"name": "DONE", "parameters": {"message": "mock 模式，已完成"}}',
        ])
    else:
        api_key = settings.llm_api_key
        if not api_key:
            typer.echo("错误: 未配置 API Key。请运行 `myagent key set` 设置后，将 key 填入配置或环境变量。", err=True)
            raise typer.Exit(code=1)
        llm = AliBailianBackend(settings=settings, api_key=api_key)

    # 工具注册
    tools = ToolRegistry()
    from myagent.tools.base import Tool

    async def _read(path: str) -> dict:
        return await read_file(path)

    async def _write(path: str, content: str) -> dict:
        return await write_file(path, content)

    async def _shell(command: str, cwd: str = "") -> dict:
        return await run_shell(command, cwd or project_path)

    tools.register(Tool(
        name="read_file", description="读取文件内容",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        execute=_read,
    ))
    tools.register(Tool(
        name="write_file", description="写入文件内容",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        execute=_write,
    ))
    tools.register(Tool(
        name="run_shell", description="执行 shell 命令",
        parameters={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]},
        execute=_shell,
    ))

    # 护栏
    guardrails = GuardrailPipeline()
    guardrails.add(PathGuardrail(project_path))
    guardrails.add(CommandGuardrail(
        blacklist=settings.command_blacklist,
        whitelist=settings.command_whitelist,
    ))

    # 反馈
    feedback = []
    if settings.feedback_run_tests:
        from myagent.feedback.test_runner import TestFeedbackRunner
        feedback.append(TestFeedbackRunner())
    if settings.feedback_run_lint:
        from myagent.feedback.linter import LintCheckerFeedback
        feedback.append(LintCheckerFeedback())

    # 主循环
    loop = AgentLoop(
        llm_backend=llm,
        tool_registry=tools,
        guardrail_pipeline=guardrails,
        feedback_checkers=feedback,
        settings=settings,
    )

    typer.echo(f"Agent 启动: {task}")
    typer.echo(f"项目路径: {project_path}")
    typer.echo()

    import asyncio
    state = asyncio.run(loop.run(task, project_path))

    typer.echo()
    typer.echo(f"状态: {state.status}")
    typer.echo(f"步数: {state.step_number}")
    if state.completion_message:
        typer.echo(f"消息: {state.completion_message}")
    typer.echo(f"对话轮次: {len(state.conversation_history)}")
