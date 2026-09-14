import json
from typing import Any

import httpx

from app.core.config import settings
from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolExecutor,
    ToolSpec,
)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url
        self._default_model = settings.ollama_model

    async def _call(
        self, messages: list[dict[str, Any]], model: str, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=120.0) as client:
            payload = {"model": model, "messages": messages, "stream": False, **(extra or {})}
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        full_messages: list[dict[str, Any]] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(dict(m) for m in messages)
        data = await self._call(full_messages, model or self._default_model)
        text = data["message"]["content"]
        return ChatResult(text=text, tokens_in=0, tokens_out=0, model=model or self._default_model)

    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT:
        schema = response_model.model_json_schema()
        instruction = (
            f"{system or ''}\n\nRespond with ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema)}"
        )
        full_messages: list[dict[str, Any]] = [{"role": "system", "content": instruction}]
        full_messages.extend(dict(m) for m in messages)
        data = await self._call(
            full_messages, model or self._default_model, extra={"format": "json"}
        )
        return response_model.model_validate_json(data["message"]["content"])

    async def tool_loop(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec],
        tool_executor: ToolExecutor,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 8,
    ) -> ChatResult:
        raise NotImplementedError(
            "OllamaProvider does not support the tool-use loop; use AnthropicProvider or FakeProvider"
        )
