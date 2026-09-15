"""Procedural memory: turns manager/analyst corrections into few-shot prompt
context for the Action and Analyst agents (T5.1). Deterministic formatting,
no LLM call -- this just shapes what earlier `Feedback` rows say into text
the next prompt can read as calibration, never as instructions to follow."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Feedback

_MAX_EXAMPLES = 5


def recent_action_feedback(session: Session, limit: int = _MAX_EXAMPLES) -> str:
    """Manager approve/reject history for drafted outbound messages."""
    rows = session.scalars(
        select(Feedback)
        .where(Feedback.kind.in_(["action_approval", "action_rejection"]))
        .order_by(Feedback.created_at.desc())
        .limit(limit)
    )
    lines: list[str] = []
    for row in rows:
        payload = row.payload or {}
        subject = (payload.get("payload") or {}).get("subject", "")
        if row.kind == "action_approval":
            lines.append(f'- Approved as drafted: "{subject}"')
        else:
            note = payload.get("feedback")
            suffix = f" -- manager said: {note}" if note else ""
            lines.append(f'- Rejected: "{subject}"{suffix}')
    return "\n".join(reversed(lines))


def record_item_correction(
    session: Session, *, item_id: uuid.UUID, chat_id: uuid.UUID, item_type: str,
    title: str, from_status: str, to_status: str, user_id: uuid.UUID,
) -> None:
    """Call when a human overrides an extracted item's `needs_review` status --
    the clearest signal of whether the Analyst's extraction was trustworthy."""
    session.add(Feedback(
        kind="item_correction", target_id=item_id, user_id=user_id,
        payload={
            "chat_id": str(chat_id), "type": item_type, "title": title,
            "from_status": from_status, "to_status": to_status,
            "accepted": to_status != "cancelled",
        },
    ))


def recent_item_corrections(session: Session, chat_id: uuid.UUID, limit: int = _MAX_EXAMPLES) -> str:
    """Human corrections to past extractions in this specific chat."""
    rows = session.scalars(
        select(Feedback).where(Feedback.kind == "item_correction")
        .order_by(Feedback.created_at.desc()).limit(limit * 4)
    )
    lines: list[str] = []
    for row in rows:
        payload = row.payload or {}
        if payload.get("chat_id") != str(chat_id):
            continue
        verdict = "confirmed as real" if payload.get("accepted") else "rejected as not a real item"
        lines.append(f'- A {payload.get("type")} titled "{payload.get("title")}" was {verdict} by a reviewer.')
        if len(lines) >= limit:
            break
    return "\n".join(lines)
