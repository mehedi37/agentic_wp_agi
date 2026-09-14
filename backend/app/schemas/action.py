import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import ActionKind, ActionStatus


class ProposedActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    escalation_id: uuid.UUID | None
    kind: ActionKind
    payload: dict
    status: ActionStatus
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    result: dict | None
    created_at: datetime
