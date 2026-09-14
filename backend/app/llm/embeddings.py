import hashlib
import random
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            # Use a stable, process-independent hash instead of Python's
            # salted str.__hash__() so the same text yields the same
            # embedding across separate process runs (e.g. `make seed` in
            # one process and `make test`/`make eval` in another).
            seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
            rng = random.Random(seed)
            vectors.append([rng.uniform(-1, 1) for _ in range(settings.embedding_dim)])
        return vectors


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(base_url=self._base_url, timeout=60.0) as client:
            for text in texts:
                response = await client.post(
                    "/api/embeddings", json={"model": self._model, "prompt": text}
                )
                response.raise_for_status()
                vectors.append(response.json()["embedding"])
        return vectors
