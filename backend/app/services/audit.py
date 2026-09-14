"""Audit-log helper (PLAN.md T0.5 deliverable).

`AuditLog` (see `app.db.models.AuditLog`) has exactly four columns: `id`
(PK), `user_id`, `action`, `details` (JSONB) and the server-defaulted `ts`.
This helper's parameters mirror those columns 1:1. Not wired into any route
yet -- that is Phase 1+ work once routes exist to call it from.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record_audit_event(
    session: Session,
    actor_id: uuid.UUID | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Insert one `audit_log` row and return the (flushed, not committed) entity.

    `actor_id` is the acting user's id, or `None` for a system-initiated
    action (e.g. an agent, a cron job). `action` is a short machine-readable
    verb (e.g. "action.approve", "item.status_change"). `details` carries
    any extra structured context -- including which target the action
    affected (e.g. `{"target_type": "item", "target_id": str(item_id)}`),
    since the table has no dedicated target columns.

    Does not commit: the caller controls the transaction boundary so this
    can be composed into a larger unit of work.
    """
    entry = AuditLog(user_id=actor_id, action=action, details=details)
    session.add(entry)
    session.flush()
    return entry
