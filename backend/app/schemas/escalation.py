import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import EscalationStatus


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule: str
    severity: str
    item_id: uuid.UUID | None
    chat_id: uuid.UUID | None
    rationale: str
    evidence: dict | None
    status: EscalationStatus
    created_at: datetime
