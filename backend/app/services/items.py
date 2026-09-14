"""Persist validated item updates without losing their evidence or history."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Item, ItemEvidence, ItemHistory, Segment
from app.schemas.item import ExtractedItem


def find_update_target(session: Session, segment: Segment, extracted: ExtractedItem) -> Item | None:
    query = select(Item).where(Item.chat_id == segment.chat_id, Item.type == extracted.type)
    if extracted.related_item_id:
        return session.scalar(query.where(Item.id == extracted.related_item_id))
    matches = list(session.scalars(query.where(
        func.lower(Item.title) == extracted.title.strip().lower(),
        Item.validation_status == "passed",
    )))
    return matches[0] if len(matches) == 1 else None


def persist_item(session: Session, segment: Segment, extracted: ExtractedItem,
                 values: dict, *, passed: bool) -> Item:
    target = find_update_target(session, segment, extracted) if passed else None
    new_status = {"completed": "done", "cancelled": "cancelled"}.get(extracted.status_hint)
    if target is None:
        item = Item(**values, status=(new_status or "open") if passed else "needs_review")
        session.add(item)
        session.flush()
    else:
        item = target
        changes = {}
        for key in ("description", "owner_participant_id", "owner_raw", "due_at", "due_raw",
                    "priority", "severity", "likelihood", "confidence"):
            value = values.get(key)
            if value is not None and getattr(item, key) != value:
                previous = getattr(item, key)
                changes[key] = {"before": str(previous) if previous is not None else None,
                                "after": str(value)}
                setattr(item, key, value)
        if new_status and item.status != new_status:
            changes["status"] = {"before": item.status, "after": new_status}
            item.status = new_status
        if changes:
            session.add(ItemHistory(item_id=item.id, change=changes, actor="agent",
                source_message_id=extracted.evidence[0].message_id if extracted.evidence else None))
    existing = {(e.message_id, e.quote) for e in session.scalars(
        select(ItemEvidence).where(ItemEvidence.item_id == item.id))}
    for evidence in extracted.evidence:
        if evidence.message_id in segment.message_ids and (evidence.message_id, evidence.quote) not in existing:
            session.add(ItemEvidence(item_id=item.id, message_id=evidence.message_id, quote=evidence.quote))
            existing.add((evidence.message_id, evidence.quote))
    session.flush()
    return item
