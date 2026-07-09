"""key 子命令 — API 凭据管理（keyring）。"""

from __future__ import annotations

import getpass
import sys

import typer

from myagent.credentials.store import CredentialStore

app = typer.Typer(help="管理 API 凭据")


@app.command()
def status():
    """显示凭据配置状态。"""
    store = CredentialStore()
    key_names = ["api_key", "embedding_api_key"]
    for name in key_names:
        if store.exists(name):
            typer.echo(f"✓ {name}: 已配置")
        else:
            typer.echo(f"✗ {name}: 未配置")


@app.command()
def set_key(
    service: str = typer.Option("api_key", "--service", "-s", help="要设置的凭据: api_key / embedding_api_key"),
):
    """交互式设置 API Key（隐藏输入）。"""
    store = CredentialStore()
    print(f"请输入 {service} (输入不会显示): ", end="", file=sys.stderr)
    value = getpass.getpass("")
    if not value.strip():
        typer.echo("输入为空，已取消")
        raise typer.Exit(code=1)
    store.set(service, value.strip())
    typer.echo(f"✓ {service} 已保存到系统凭据管理器")


@app.command()
def clear(
    service: str = typer.Option("api_key", "--service", "-s", help="要清除的凭据"),
):
    """清除已保存的凭据。"""
    store = CredentialStore()
    if not store.exists(service):
        typer.echo(f"{service} 未配置，无需清除")
        return
    confirmed = typer.confirm(f"确认清除 {service}?")
    if confirmed:
        store.delete(service)
        typer.echo(f"✓ {service} 已清除")
