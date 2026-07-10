"""Docker 沙箱执行器 — 在隔离容器中执行 shell 命令。"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

try:
    import docker
    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False


SANDBOX_IMAGE = "python:3.12-slim"


class DockerSandbox:
    """在 Docker 容器中隔离执行 shell 命令。

    Docker 不可用时自动回退到本地 subprocess 执行
    （安全校验仍由 CommandGuardrail 负责）。
    """

    def __init__(self, project_path: str, image: str = SANDBOX_IMAGE):
        if not project_path:
            raise ValueError("project_path 不能为空")
        self._project_path = str(Path(project_path).absolute())
        self._image = image
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        if not _DOCKER_AVAILABLE:
            return
        try:
            self._client = docker.from_env()
            self._client.ping()
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def run(self, command: str, timeout: int = 60) -> dict:
        """在沙箱中执行命令，Docker 不可用时回退到 subprocess。"""
        if self._available:
            return await self._run_in_container(command, timeout)
        return await self._run_fallback(command, timeout)

    async def _run_in_container(self, command: str, timeout: int) -> dict:
        start = time.monotonic()
        try:
            container = self._client.containers.run(
                image=self._image,
                command=f"/bin/sh -c {_quote(command)}",
                detach=True,
                remove=False,
                mem_limit="256m",
                network_mode="none",
                read_only=True,
                volumes={self._project_path: {"bind": "/workspace", "mode": "ro"}},
                working_dir="/workspace",
            )
            try:
                exit_info = container.wait(timeout=timeout)
                exit_code = exit_info.get("StatusCode", -1)
                logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            finally:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "command": command,
                "exit_code": exit_code,
                "stdout": logs[-5000:],
                "stderr": "",
                "duration_ms": duration_ms,
                "sandbox": "docker",
            }
        except Exception as exc:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"沙箱执行失败: {exc}",
                "duration_ms": int((time.monotonic() - start) * 1000),
                "sandbox": "docker",
            }

    async def _run_fallback(self, command: str, timeout: int) -> dict:
        start = time.monotonic()
        try:
            result = subprocess.run(
                command, shell=True, cwd=self._project_path,
                capture_output=True, text=True, timeout=timeout,
            )
            return {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-2000:],
                "duration_ms": int((time.monotonic() - start) * 1000),
                "sandbox": "fallback",
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"命令超时 ({timeout}s)",
                "duration_ms": timeout * 1000,
                "sandbox": "fallback",
            }


def _quote(s: str) -> str:
    """简单 shell 引号包裹。"""
    return f"'{s}'" if "'" not in s else f'"{s}"'
