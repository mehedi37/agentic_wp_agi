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


@pytest.mark.asyncio
async def test_chat_result_carries_latency() -> None:
    provider = FakeProvider(responses=["ok"])
    result = await provider.chat([{"role": "user", "content": "hi"}])
    assert isinstance(result.latency_ms, int)
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_interleaved_chat_and_structured_calls_do_not_scramble_scripts() -> None:
    # Regression test for the shared-cursor bug: chat and structured used to
    # share one `call_count`, so alternating calls (as the Analyst<->Validator
    # retry loop does) would skip entries in each other's script.
    provider = FakeProvider(
        responses=["chat-1", "chat-2", "chat-3"],
        structured_responses=[
            {"passed": False, "reason": "first pass fails"},
            {"passed": True, "reason": "second pass ok"},
        ],
    )

    chat_1 = await provider.chat([{"role": "user", "content": "x"}])
    structured_1 = await provider.structured(
        [{"role": "user", "content": "x"}], response_model=Verdict
    )
    chat_2 = await provider.chat([{"role": "user", "content": "x"}])
    structured_2 = await provider.structured(
        [{"role": "user", "content": "x"}], response_model=Verdict
    )
    chat_3 = await provider.chat([{"role": "user", "content": "x"}])

    assert [chat_1.text, chat_2.text, chat_3.text] == ["chat-1", "chat-2", "chat-3"]
    assert structured_1.passed is False
    assert structured_1.reason == "first pass fails"
    assert structured_2.passed is True
    assert structured_2.reason == "second pass ok"


@pytest.mark.asyncio
async def test_tool_loop_invokes_tool_executor_with_scripted_calls() -> None:
    executed: list[tuple[str, dict]] = []

    async def tool_executor(name: str, tool_input: dict) -> str:
        executed.append((name, tool_input))
        return f"result-for-{name}"

    provider = FakeProvider(
        tool_loop_calls=[
            [("resolve_date", {"raw": "kal"}), ("resolve_participant", {"name": "Rafi"})],
        ],
        tool_loop_responses=["final answer"],
    )

    result = await provider.tool_loop(
        [{"role": "user", "content": "when is it due"}],
        tools=[],
        tool_executor=tool_executor,
    )

    assert executed == [
        ("resolve_date", {"raw": "kal"}),
        ("resolve_participant", {"name": "Rafi"}),
    ]
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].name == "resolve_date"
    assert result.tool_calls[0].output == "result-for-resolve_date"
    assert result.text == "final answer"


@pytest.mark.asyncio
async def test_tool_loop_has_its_own_cursor_independent_of_chat() -> None:
    executed: list[str] = []

    async def tool_executor(name: str, tool_input: dict) -> str:
        executed.append(name)
        return "ok"

    provider = FakeProvider(
        responses=["chat-response"],
        tool_loop_calls=[[("tool_a", {})], [("tool_b", {})]],
        tool_loop_responses=["loop-1", "loop-2"],
    )

    chat_result = await provider.chat([{"role": "user", "content": "hi"}])
    loop_1 = await provider.tool_loop(
        [{"role": "user", "content": "hi"}], tools=[], tool_executor=tool_executor
    )
    loop_2 = await provider.tool_loop(
        [{"role": "user", "content": "hi"}], tools=[], tool_executor=tool_executor
    )

    assert chat_result.text == "chat-response"
    assert loop_1.text == "loop-1"
    assert loop_2.text == "loop-2"
    assert executed == ["tool_a", "tool_b"]


@pytest.mark.asyncio
async def test_on_call_hook_receives_chat_results() -> None:
    received = []
    provider = FakeProvider(responses=["hi"], on_call=received.append)
    result = await provider.chat([{"role": "user", "content": "hi"}])
    assert received == [result]
