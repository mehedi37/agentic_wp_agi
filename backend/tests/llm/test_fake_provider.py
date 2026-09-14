import pytest
from pydantic import BaseModel

from app.llm.fake_provider import FakeProvider


class Verdict(BaseModel):
    passed: bool
    reason: str


@pytest.mark.asyncio
async def test_chat_cycles_through_scripted_responses() -> None:
    provider = FakeProvider(responses=["first", "second"])
    r1 = await provider.chat([{"role": "user", "content": "hi"}])
    r2 = await provider.chat([{"role": "user", "content": "hi"}])
    r3 = await provider.chat([{"role": "user", "content": "hi"}])
    assert [r1.text, r2.text, r3.text] == ["first", "second", "first"]
    assert provider.call_count == 3


@pytest.mark.asyncio
async def test_chat_without_script_echoes_last_user_message() -> None:
    provider = FakeProvider()
    result = await provider.chat([{"role": "user", "content": "hello there"}])
    assert result.text == "FAKE: hello there"


@pytest.mark.asyncio
async def test_structured_validates_into_response_model() -> None:
    provider = FakeProvider(structured_responses=[{"passed": True, "reason": "looks good"}])
    verdict = await provider.structured([{"role": "user", "content": "check"}], response_model=Verdict)
    assert verdict.passed is True
    assert verdict.reason == "looks good"
