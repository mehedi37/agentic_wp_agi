import time
from collections.abc import Callable
from typing import cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam

from app.core.config import settings
from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolCallRecord,
    ToolExecutor,
    ToolSpec,
)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, on_call: Callable[[ChatResult], None] | None = None) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._default_model = settings.anthropic_model
        self._on_call = on_call

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        # NOTE: the installed anthropic SDK (client for the current Claude model
        # generation) no longer accepts a `temperature` keyword on messages.create
        # (adaptive reasoning replaced manual temperature control), so it is
        # accepted here for interface compatibility with LLMProvider but not
        # forwarded to the API call.
        start = time.perf_counter()
        response = await self._client.messages.create(
            model=model or self._default_model,
            max_tokens=4096,
            system=system or "",
            messages=cast(
                list[MessageParam],
                [{"role": m["role"], "content": m["content"]} for m in messages],
            ),
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        text = "".join(block.text for block in response.content if block.type == "text")
        result = ChatResult(
            text=text,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            model=response.model,
            latency_ms=latency_ms,
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
        tool = {
            "name": "emit_result",
            "description": "Emit the structured result.",
            "input_schema": response_model.model_json_schema(),
        }
        response = await self._client.messages.create(
            model=model or self._default_model,
            max_tokens=4096,
            system=system or "",
            messages=cast(
                list[MessageParam],
                [{"role": m["role"], "content": m["content"]} for m in messages],
            ),
            tools=cast(list[ToolParam], [tool]),
            tool_choice={"type": "tool", "name": "emit_result"},
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        return response_model.model_validate(tool_use.input)

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
        anthropic_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        conversation: list[dict] = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        tool_calls: list[ToolCallRecord] = []
        last_response = None

        start = time.perf_counter()
        for _ in range(max_steps):
            last_response = await self._client.messages.create(
                model=model or self._default_model,
                max_tokens=4096,
                system=system or "",
                messages=cast(list[MessageParam], conversation),
                tools=cast(list[ToolParam], anthropic_tools),
            )
            conversation.append({"role": "assistant", "content": last_response.content})

            if last_response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in last_response.content:
                if block.type != "tool_use":
                    continue
                output = await tool_executor(block.name, block.input)
                tool_calls.append(ToolCallRecord(name=block.name, input=block.input, output=output))
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": output}
                )
            conversation.append({"role": "user", "content": tool_results})

        latency_ms = int((time.perf_counter() - start) * 1000)
        assert last_response is not None
        text = "".join(b.text for b in last_response.content if b.type == "text")
        result = ChatResult(
            text=text,
            tokens_in=last_response.usage.input_tokens,
            tokens_out=last_response.usage.output_tokens,
            model=last_response.model,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )
        if self._on_call is not None:
            self._on_call(result)
        return result
