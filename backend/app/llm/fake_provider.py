from typing import Any

from pydantic import BaseModel

from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolExecutor,
    ToolSpec,
)


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(
        self,
        responses: list[str] | None = None,
        structured_responses: list[BaseModel | dict] | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._structured_responses = list(structured_responses or [])
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def _next_text(self, messages: list[ChatMessage]) -> str:
        if self._responses:
            return self._responses[self.call_count % len(self._responses)]
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"FAKE: {last_user}"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        self.calls.append({"method": "chat", "messages": messages, "system": system})
        text = self._next_text(messages)
        self.call_count += 1
        return ChatResult(text=text, tokens_in=0, tokens_out=0, model=model or "fake-model")

    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT:
        self.calls.append({"method": "structured", "messages": messages, "system": system})
        if not self._structured_responses:
            raise ValueError("FakeProvider has no scripted structured_responses left")
        idx = self.call_count % len(self._structured_responses)
        raw = self._structured_responses[idx]
        self.call_count += 1
        if isinstance(raw, response_model):
            return raw
        return response_model.model_validate(raw)

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
        self.calls.append({"method": "tool_loop", "messages": messages, "system": system})
        text = self._next_text(messages)
        self.call_count += 1
        return ChatResult(text=text, tokens_in=0, tokens_out=0, model=model or "fake-model")
