import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SegmentOut(BaseModel):
    """Mirrors the `segments` table (see `app.db.models.Segment`).

    A segment groups a chat's messages into one conversational unit (a time
    gap over 45 minutes or a topic shift closes a segment) that the Analyst
    agent classifies and extracts items from.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: uuid.UUID
    start_ts: datetime
    end_ts: datetime
    message_ids: list[uuid.UUID] = Field(default_factory=list)
    topic: str | None = None
    category: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    summary: str | None = None
    analysis_status: str
