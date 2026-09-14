from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingProvider, FakeEmbeddingProvider, OllamaEmbeddingProvider
from app.llm.fake_provider import FakeProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider
    if provider == "fake":
        return FakeProvider()
    if provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider
    if provider == "fake":
        return FakeEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    raise ValueError(f"Unknown embedding provider: {provider!r}")
