"""Idempotent, source-cited daily and weekly memory rollups."""
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Entity, Item, Message, Participant, Summary
from app.llm.embeddings import EmbeddingProvider


async def consolidate_memory(session: Session, embedder: EmbeddingProvider) -> dict:
    # Serialize cron retries and manual invocations for idempotent upserts.
    session.execute(text("SELECT pg_advisory_xact_lock(731204)"))
    tz = ZoneInfo(settings.app_timezone)
    groups: dict[tuple[uuid.UUID, datetime], list[Message]] = defaultdict(list)
    for message in session.scalars(select(Message).where(Message.is_system.is_(False)).order_by(Message.ts)):
        day = message.ts.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        groups[(message.chat_id, day)].append(message)
    changed = 0

    async def upsert(scope: str, chat_id: uuid.UUID, start: datetime, end: datetime, body: str) -> None:
        nonlocal changed
        row = session.scalar(select(Summary).where(Summary.scope == scope,
            Summary.scope_id == str(chat_id), Summary.period_start == start))
        if row is None:
            row = Summary(scope=scope, scope_id=str(chat_id), period_start=start, period_end=end, text=body)
            session.add(row)
        elif row.text == body:
            return
        row.text = body
        [row.embedding] = await embedder.embed([body])
        changed += 1

    weekly: dict[tuple[uuid.UUID, datetime], list[str]] = defaultdict(list)
    for (chat_id, day), messages in groups.items():
        body = "\n".join(f"{m.text} [{m.id}]" for m in messages)
        await upsert("day", chat_id, day, day + timedelta(days=1), body)
        week = day - timedelta(days=day.weekday())
        weekly[(chat_id, week)].append(f"{day.date()}\n{body}")
    for (chat_id, week), days in weekly.items():
        await upsert("week", chat_id, week, week + timedelta(days=7), "\n\n".join(days))
    profiles = 0
    # Group by display name so the same person mentioned across multiple
    # chats gets one merged profile/workload instead of one per chat.
    by_name: dict[str, list[Participant]] = defaultdict(list)
    for participant in session.scalars(select(Participant)):
        by_name[participant.display_name].append(participant)
    for name, group in by_name.items():
        entity = next(
            (session.get(Entity, p.entity_id) for p in group if p.entity_id and session.get(Entity, p.entity_id)),
            None,
        ) or session.scalar(select(Entity).where(Entity.kind == "person", Entity.name == name))
        if entity is None:
            entity = Entity(kind="person", name=name, aliases=[])
            session.add(entity)
            session.flush()
        for participant in group:
            participant.entity_id = entity.id
        participant_ids = [p.id for p in group]
        active = list(session.scalars(select(Item).where(
            Item.owner_participant_id.in_(participant_ids), Item.status.notin_(["done", "cancelled"])
        )))
        profile = {
            "chat_ids": sorted({str(p.chat_id) for p in group}),
            "active_items": [
                {"id": str(i.id), "title": i.title, "status": i.status, "chat_id": str(i.chat_id)} for i in active
            ],
        }
        if entity.profile != profile:
            entity.profile = profile
            profiles += 1
    stale = list(session.scalars(select(Item).where(Item.updated_at < datetime.now(UTC) - timedelta(days=14),
        Item.status.in_(["open", "in_progress"]))))
    # Preserve management status; flag for the analyst review queue.
    for item in stale:
        item.validation_status = "needs_review"
    session.flush()
    return {"summaries_updated": changed, "profiles_updated": profiles, "stale_items": len(stale)}
