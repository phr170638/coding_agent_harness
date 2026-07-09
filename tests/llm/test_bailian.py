"""阿里百炼 Backend 集成测试 — 需要真实 API key，无 key 时自动跳过。"""

import os

import pytest

from myagent.config.settings import Settings
from myagent.credentials.store import CredentialStore
from myagent.llm.bailian import AliBailianBackend


def _get_credentials():
    """尝试从 keyring 或环境变量获取 API key。"""
    store = CredentialStore()
    key = store.get("api_key")
    if not key:
        key = os.environ.get("MYAGENT_LLM_API_KEY", "")
    if not key:
        key = os.environ.get("DASHSCOPE_API_KEY", "")
    return key


pytestmark = pytest.mark.skipif(
    not _get_credentials(),
    reason="未配置 API key，跳过集成测试。运行 myagent key set 或设置环境变量。",
)


class TestAliBailianBackend:
    """阿里百炼 Backend 集成测试。"""

    async def test_simple_chat(self):
        api_key = _get_credentials()
        settings = Settings()
        backend = AliBailianBackend(settings=settings, api_key=api_key)

        context = "你是一个编码助手。用户需求：在 main.py 中实现一个 hello 函数。"
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取项目中的文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"}
                        },
                        "required": ["path"],
                    },
                },
            }
        ]

        response = await backend.decide(context, tools)
        assert response is not None
        assert len(response) > 0

    async def test_function_calling(self):
        """LLM 在工具调用场景下应返回有效的 function call JSON。"""
        api_key = _get_credentials()
        settings = Settings()
        backend = AliBailianBackend(settings=settings, api_key=api_key)

        context = "用户要求读取 app.py 的内容。请直接调用 read_file 工具。"
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"}
                        },
                        "required": ["path"],
                    },
                },
            }
        ]

        response = await backend.decide(context, tools)
        assert response is not None
        # 响应应包含可解析的 action 信息
        assert "read_file" in response.lower() or "path" in response.lower()

    async def test_timeout_config(self):
        """超时配置应正确传递。"""
        api_key = _get_credentials()
        settings = Settings(llm_timeout=10)
        backend = AliBailianBackend(settings=settings, api_key=api_key)
        assert backend._client.timeout == 10
