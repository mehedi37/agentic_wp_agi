import pytest

from app.core.config import settings
from app.llm.factory import get_embedding_provider, get_llm_provider
from app.llm.fake_provider import FakeProvider


def test_get_llm_provider_returns_fake_by_default() -> None:
    assert settings.llm_provider == "fake"
    provider = get_llm_provider()
    assert isinstance(provider, FakeProvider)


def test_get_llm_provider_raises_on_unknown() -> None:
    original = settings.llm_provider
    settings.llm_provider = "not-a-real-provider"
    try:
        with pytest.raises(ValueError):
            get_llm_provider()
    finally:
        settings.llm_provider = original


def test_get_embedding_provider_default_is_fake_when_configured() -> None:
    original = settings.embedding_provider
    settings.embedding_provider = "fake"
    try:
        provider = get_embedding_provider()
        assert provider.name == "fake"
    finally:
        settings.embedding_provider = original
