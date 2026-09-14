from app.llm.embeddings import FakeEmbeddingProvider


async def test_fake_embedding_provider_is_stable_across_instances() -> None:
    # Simulates cross-process stability: two independently constructed
    # providers (standing in for two separate process runs, e.g. `make seed`
    # and `make test`) must embed identical text to identical vectors.
    provider_a = FakeEmbeddingProvider()
    provider_b = FakeEmbeddingProvider()

    text = "The invoice for Padma Warehouse is overdue."
    [vector_a] = await provider_a.embed([text])
    [vector_b] = await provider_b.embed([text])

    assert vector_a == vector_b


async def test_fake_embedding_provider_differs_for_different_text() -> None:
    provider = FakeEmbeddingProvider()
    [vector_1] = await provider.embed(["hello"])
    [vector_2] = await provider.embed(["goodbye"])

    assert vector_1 != vector_2
