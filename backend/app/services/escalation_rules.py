"""Deterministic detector rules for the Monitor agent (PLAN.md §6.4).

Each `detect_*` function inspects current DB state and returns a list of
`EscalationCandidate` for conditions that should raise a new escalation
(the caller, `app.agents.monitor.run_monitor`, dedupes against already-open
escalations before inserting). No LLM call in this module -- these are the
rules-based detectors; PLAN.md's "decision reversed" and "manager question
unanswered" detectors need LLM reasoning / richer data modeling than this
phase's Item dedup (not yet implemented) supports, and are deferred.
"""
import difflib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Item, Segment
from app.services.rules import rule_config

_RECURRING_WINDOW_DAYS = 7
_RECURRING_MIN_COUNT = 3
_RECURRING_TITLE_SIMILARITY = 0.6
_SENTIMENT_DIP_STREAK = 3


@dataclass
class EscalationCandidate:
    rule: str
    severity: str
    rationale: str
    item_id: uuid.UUID | None = None
    chat_id: uuid.UUID | None = None
    evidence: list[dict] | None = None


def detect_overdue_actions(session: Session, *, chat_id: uuid.UUID | None = None) -> list[EscalationCandidate]:
    now = datetime.now(tz=UTC)
    query = select(Item).where(
        Item.type == "action",
        Item.status.notin_(["done", "cancelled"]),
        Item.due_at.is_not(None),
        Item.due_at < now,
    )
    if chat_id is not None:
        query = query.where(Item.chat_id == chat_id)

    candidates = []
    for item in session.scalars(query):
        assert item.due_at is not None  # guaranteed by the query's Item.due_at.is_not(None) filter
        candidates.append(
            EscalationCandidate(
                rule="overdue_action",
                severity="high",
                rationale=f'Action "{item.title}" was due {item.due_at.isoformat()} and is still {item.status}.',
                item_id=item.id,
                chat_id=item.chat_id,
            )
        )
    return candidates


def detect_unowned_high_risk(session: Session, *, chat_id: uuid.UUID | None = None) -> list[EscalationCandidate]:
    query = select(Item).where(
        Item.type == "risk",
        Item.severity == "high",
        Item.status.notin_(["done", "cancelled"]),
        Item.owner_participant_id.is_(None),
        (Item.owner_raw.is_(None)) | (Item.owner_raw == ""),
    )
    if chat_id is not None:
        query = query.where(Item.chat_id == chat_id)

    return [
        EscalationCandidate(
            rule="unowned_high_risk",
            severity="high",
            rationale=f'High-severity risk "{item.title}" has no assigned owner.',
            item_id=item.id,
            chat_id=item.chat_id,
        )
        for item in session.scalars(query)
    ]


def detect_recurring_issue(session: Session, *, chat_id: uuid.UUID | None = None) -> list[EscalationCandidate]:
    _, params = rule_config(session, "recurring_issue")
    window_days, min_count = params["window_days"], params["min_count"]
    query = select(Item, Segment.end_ts).join(Segment, Item.segment_id == Segment.id).where(Item.type == "issue")
    if chat_id is not None:
        query = query.where(Item.chat_id == chat_id)
    rows = list(session.execute(query).all())

    candidates: list[EscalationCandidate] = []
    seen_clusters: set[frozenset] = set()
    for item, ts in rows:
        cluster = [
            (other_item, other_ts)
            for other_item, other_ts in rows
            if other_item.chat_id == item.chat_id
            and abs(other_ts - ts) <= timedelta(days=window_days)
            and difflib.SequenceMatcher(None, other_item.title.lower(), item.title.lower()).ratio()
            >= _RECURRING_TITLE_SIMILARITY
        ]
        if len(cluster) < min_count:
            continue
        key = frozenset(c[0].id for c in cluster)
        if key in seen_clusters:
            continue
        seen_clusters.add(key)
        latest_item = max(cluster, key=lambda c: c[1])[0]
        candidates.append(
            EscalationCandidate(
                rule="recurring_issue",
                severity="medium",
                rationale=f'Issue "{latest_item.title}" raised {len(cluster)} times within '
                f"{window_days} days.",
                item_id=latest_item.id,
                chat_id=latest_item.chat_id,
            )
        )
    return candidates


def detect_sentiment_dip(session: Session, *, chat_id: uuid.UUID | None = None) -> list[EscalationCandidate]:
    streak = rule_config(session, "sentiment_dip")[1]["streak"]
    query = select(Segment).order_by(Segment.chat_id, Segment.end_ts.desc())
    if chat_id is not None:
        query = query.where(Segment.chat_id == chat_id)
    segments = list(session.scalars(query))

    by_chat: dict[uuid.UUID, list[Segment]] = {}
    for seg in segments:
        by_chat.setdefault(seg.chat_id, []).append(seg)

    candidates = []
    for cid, chat_segments in by_chat.items():
        recent = chat_segments[:streak]
        if len(recent) == streak and all(s.sentiment == "negative" for s in recent):
            candidates.append(
                EscalationCandidate(
                    rule="sentiment_dip",
                    severity="medium",
                    rationale=f"Last {streak} segments in this chat were negative in a row.",
                    chat_id=cid,
                )
            )
    return candidates
