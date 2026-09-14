from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, TypedDict, TypeVar

from pydantic import BaseModel

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCallRecord:
    name: str
    input: dict
    output: str


@dataclass
class ChatResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


ToolExecutor = Callable[[str, dict], Awaitable[str]]


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult: ...

    @abstractmethod
    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT: ...

    @abstractmethod
    async def tool_loop(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec],
        tool_executor: ToolExecutor,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 8,
    ) -> ChatResult: ...
