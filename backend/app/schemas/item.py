import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import ItemStatus, ItemType, StatusHint


class EvidenceRef(BaseModel):
    message_id: uuid.UUID
    quote: str


class ExtractedItem(BaseModel):
    type: ItemType
    title: str
    description: str | None = None
    owner_raw: str | None = None
    owner_participant_id: uuid.UUID | None = None
    due_date_raw: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    severity: str | None = None
    likelihood: str | None = None
    status_hint: StatusHint = "new"
    related_item_id: uuid.UUID | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ItemType
    title: str
    description: str | None
    chat_id: uuid.UUID
    owner_participant_id: uuid.UUID | None
    owner_raw: str | None
    due_at: datetime | None
    due_raw: str | None
    status: ItemStatus
    priority: str | None
    severity: str | None
    likelihood: str | None
    confidence: float | None
    created_at: datetime
    updated_at: datetime
