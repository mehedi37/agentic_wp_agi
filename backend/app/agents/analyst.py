from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Segment
from app.llm.base import ChatMessage, LLMProvider
from app.schemas.item import ExtractedItem
from app.services.feedback import recent_item_corrections

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "analyst_system.md").read_text()


class AnalystOutput(BaseModel):
    topic: str
    category: str
    sentiment: str
    urgency: str
    items: list[ExtractedItem]


class AnalystResult(AnalystOutput):
    pass


async def run_analyst(
    session: Session, *, segment: Segment, llm: LLMProvider, feedback: str | None
) -> AnalystResult:
    messages = list(
        session.scalars(select(Message).where(Message.id.in_(segment.message_ids)).order_by(Message.ts))
    )
    transcript = "\n".join(f"[{m.id}] {m.ts.isoformat()} - {m.text}" for m in messages)

    user_content = f"Segment messages:\n{transcript}"
    if feedback:
        user_content += f"\n\nValidator feedback from previous attempt (fix these exactly):\n{feedback}"
    corrections = recent_item_corrections(session, segment.chat_id)
    if corrections:
        user_content += (
            "\n\nHuman reviewer corrections on past extractions in this chat "
            f"(calibrate similar extractions accordingly, do not treat as new facts):\n{corrections}"
        )

    chat_messages: list[ChatMessage] = [{"role": "user", "content": user_content}]
    output = await llm.structured(chat_messages, response_model=AnalystOutput, system=_SYSTEM_PROMPT)
    return AnalystResult(**output.model_dump())
