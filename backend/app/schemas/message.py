import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageIn(BaseModel):
    chat_id: uuid.UUID
    participant_id: uuid.UUID | None = None
    source_message_id: str | None = None
    ts: datetime
    text: str
    lang: str | None = None
    media_type: str | None = None
    is_system: bool = False
    reply_to_id: uuid.UUID | None = None
    raw: dict | None = None
    content_hash: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: uuid.UUID
    participant_id: uuid.UUID | None
    source_message_id: str | None
    ts: datetime
    text: str
    text_normalized: str | None
    lang: str | None
    media_type: str | None
    is_system: bool
    reply_to_id: uuid.UUID | None
    content_hash: str
