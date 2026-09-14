from typing import Literal

ItemType = Literal["action", "decision", "risk", "issue"]
ItemStatus = Literal["open", "in_progress", "done", "cancelled", "needs_review"]
Role = Literal["manager", "analyst"]
EscalationStatus = Literal["open", "acknowledged", "resolved", "auto_closed"]
ActionKind = Literal["notify", "email", "whatsapp", "status_update"]
ActionStatus = Literal["pending", "approved", "rejected", "executing", "executed", "failed"]
StatusHint = Literal["new", "update", "completed", "cancelled"]
