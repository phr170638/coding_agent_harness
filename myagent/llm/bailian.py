"""阿里百炼 LLM Backend — 通过 OpenAI-compatible API 调用通义千问系列模型。"""

import json
import logging

from openai import AsyncOpenAI

from myagent.config.settings import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个编码助手 Agent。你需要根据当前上下文决定下一步操作。

你的输出必须是严格的 JSON 格式：
```json
{"action": "<工具名称>", "parameters": {<参数>}}
```

当任务已完成时，输出：
```json
{"action": "DONE", "summary": "<完成总结>"}
```

可用工具及描述会在每条消息中提供。请仔细阅读上下文，做出合理的下一步决策。"""


class AliBailianBackend:
    """阿里百炼 LLM 后端，使用 OpenAI-compatible API。

    Attributes:
        _client: AsyncOpenAI 客户端实例。
    """

    def __init__(self, settings: Settings, api_key: str) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=settings.llm_base_url,
            timeout=float(settings.llm_timeout),
        )
        self._model = settings.llm_model

    async def decide(self, context: str, tools: list[dict]) -> str:
        """调用 LLM 决策下一步动作。

        Args:
            context: 完整上下文（任务、历史、项目状态）。
            tools: 可用工具的 OpenAI function calling schema。

        Returns:
            LLM 的原始响应文本。
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools if tools else None,
                temperature=0.1,
                max_tokens=4096,
            )
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            return json.dumps({"action": "ERROR", "error": str(e)})

        choice = response.choices[0]
        message = choice.message

        # 优先使用 function call
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            return json.dumps({
                "action": tool_call.function.name,
                "parameters": json.loads(tool_call.function.arguments),
            })

        # 解析纯文本中的 JSON
        content = message.content or ""
        return content.strip()
