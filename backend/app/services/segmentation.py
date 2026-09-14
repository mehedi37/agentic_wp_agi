import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Segment


class _HasTsAndId(Protocol):
    id: uuid.UUID
    ts: datetime


@dataclass
class SegmentDraft:
    start_ts: datetime
    end_ts: datetime
    message_ids: list[uuid.UUID] = field(default_factory=list)


def build_segments(
    messages: Sequence[_HasTsAndId], *, gap_minutes: int = 45, max_messages: int = 60
) -> list[SegmentDraft]:
    """A segment closes on a time gap over `gap_minutes` or once it holds
    `max_messages`, whichever comes first (PLAN.md §4.1). Deterministic --
    no LLM call; topic coherence in practice comes from the time-gap rule."""
    if not messages:
        return []
    ordered = sorted(messages, key=lambda m: m.ts)
    gap = timedelta(minutes=gap_minutes)

    drafts: list[SegmentDraft] = []
    current = SegmentDraft(start_ts=ordered[0].ts, end_ts=ordered[0].ts, message_ids=[ordered[0].id])

    for prev, msg in pairwise(ordered):
        exceeds_gap = (msg.ts - prev.ts) > gap
        exceeds_count = len(current.message_ids) >= max_messages
        if exceeds_gap or exceeds_count:
            drafts.append(current)
            current = SegmentDraft(start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id])
        else:
            current.end_ts = msg.ts
            current.message_ids.append(msg.id)
    drafts.append(current)
    return drafts


def persist_pending_segments(session: Session, chat_id: uuid.UUID) -> list[Segment]:
    """Segments every message in `chat_id` newer than the chat's latest
    existing segment (or every message if none exist yet), in `ts` order.
    Safe to call repeatedly per incoming batch."""
    latest_end = session.scalar(
        select(Segment.end_ts).where(Segment.chat_id == chat_id).order_by(Segment.end_ts.desc()).limit(1)
    )
    query = select(Message).where(Message.chat_id == chat_id, Message.is_system.is_(False))
    if latest_end is not None:
        query = query.where(Message.ts > latest_end)
    pending = list(session.scalars(query.order_by(Message.ts)))

    drafts = build_segments(pending, gap_minutes=45, max_messages=60)
    segments = [
        Segment(
            chat_id=chat_id,
            start_ts=d.start_ts,
            end_ts=d.end_ts,
            message_ids=d.message_ids,
            analysis_status="pending",
        )
        for d in drafts
    ]
    session.add_all(segments)
    session.flush()
    return segments
