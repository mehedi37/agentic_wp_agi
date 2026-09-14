import uuid

from app.agents.analyst import AnalystOutput
from app.llm.demo_provider import DemoProvider


async def test_demo_extracts_grounded_low_confidence_candidate():
    mid = str(uuid.uuid4())
    result = await DemoProvider().structured(
        [{"role": "user", "content": f"[{mid}] 2026-09-14T10:00:00 - Please review the report"}],
        response_model=AnalystOutput,
    )
    assert len(result.items) == 1
    assert str(result.items[0].evidence[0].message_id) == mid
    assert result.items[0].confidence < 0.6


async def test_demo_does_not_invent_items_from_small_talk():
    result = await DemoProvider().structured(
        [{"role": "user", "content": f"[{uuid.uuid4()}] 2026-09-14T10:00:00 - hello"}],
        response_model=AnalystOutput,
    )
    assert result.items == []
