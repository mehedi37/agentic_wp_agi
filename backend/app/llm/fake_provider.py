import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolCallRecord,
    ToolExecutor,
    ToolSpec,
)


class FakeProvider(LLMProvider):
    """Deterministic, scripted LLM provider for tests.

    `chat`, `structured` and `tool_loop` each keep their own independent
    cursor into their own scripted-response list, so interleaved calls
    (e.g. an Analyst<->Validator retry loop alternating `structured` calls,
    or a ReAct loop alternating `tool_loop` and `chat`) never scramble each
    other's script.
    """

    name = "fake"

    def __init__(
        self,
        responses: list[str] | None = None,
        structured_responses: list[BaseModel | dict] | None = None,
        tool_loop_calls: list[list[tuple[str, dict]]] | None = None,
        tool_loop_responses: list[str] | None = None,
        on_call: Callable[[ChatResult], None] | None = None,
    ) -> None:
        self._chat_responses = list(responses or [])
        self._structured_responses = list(structured_responses or [])
        # Each entry scripts one `tool_loop()` invocation: the sequence of
        # (tool_name, tool_input) pairs that invocation should drive through
        # `tool_executor` before returning its final text.
        self._tool_loop_calls = list(tool_loop_calls or [])
        self._tool_loop_responses = list(tool_loop_responses or responses or [])

        self._chat_cursor = 0
        self._structured_cursor = 0
        self._tool_loop_cursor = 0

        self._on_call = on_call
        self.calls: list[dict[str, Any]] = []

    @property
    def call_count(self) -> int:
        """Total calls across all methods (kept for backward compatibility)."""
        return self._chat_cursor + self._structured_cursor + self._tool_loop_cursor

    @staticmethod
    def _last_user_text(messages: list[ChatMessage]) -> str:
        return next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    def _scripted_text(self, script: list[str], cursor: int, messages: list[ChatMessage]) -> str:
        if script:
            return script[cursor % len(script)]
        return f"FAKE: {self._last_user_text(messages)}"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        self.calls.append({"method": "chat", "messages": messages, "system": system})
        start = time.perf_counter()
        text = self._scripted_text(self._chat_responses, self._chat_cursor, messages)
        self._chat_cursor += 1
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = ChatResult(
            text=text, tokens_in=0, tokens_out=0, model=model or "fake-model", latency_ms=latency_ms
        )
        if self._on_call is not None:
            self._on_call(result)
        return result

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
        idx = self._structured_cursor % len(self._structured_responses)
        raw = self._structured_responses[idx]
        self._structured_cursor += 1
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
        start = time.perf_counter()

        tool_calls: list[ToolCallRecord] = []
        if self._tool_loop_calls:
            idx = self._tool_loop_cursor % len(self._tool_loop_calls)
            scripted_calls = self._tool_loop_calls[idx]
            for tool_name, tool_input in scripted_calls[:max_steps]:
                output = await tool_executor(tool_name, tool_input)
                tool_calls.append(ToolCallRecord(name=tool_name, input=tool_input, output=output))

        text = self._scripted_text(self._tool_loop_responses, self._tool_loop_cursor, messages)
        self._tool_loop_cursor += 1
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = ChatResult(
            text=text,
            tokens_in=0,
            tokens_out=0,
            model=model or "fake-model",
            tool_calls=tool_calls,
            latency_ms=latency_ms,
        )
        if self._on_call is not None:
            self._on_call(result)
        return result
