from collections.abc import Callable

from app.core.config import settings
from app.llm.base import ChatResult, LLMProvider
from app.llm.embeddings import EmbeddingProvider, FakeEmbeddingProvider, OllamaEmbeddingProvider
from app.llm.fake_provider import FakeProvider


def get_llm_provider(on_call: Callable[[ChatResult], None] | None = None) -> LLMProvider:
    """Build the configured LLM provider.

    `on_call`, when given, is invoked by the provider with the `ChatResult`
    of every completed `chat`/`tool_loop` call (token counts, latency,
    model). It is a plain callback hook only — this module stays decoupled
    from the database on purpose, so a later phase can wire `on_call` up to
    write `agent_runs` rows without touching provider internals again.
    """
    provider = settings.llm_provider
    if provider == "fake":
        return FakeProvider(on_call=on_call)
    if provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(on_call=on_call)
    if provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(on_call=on_call)
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider
    if provider == "fake":
        return FakeEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    raise ValueError(f"Unknown embedding provider: {provider!r}")
