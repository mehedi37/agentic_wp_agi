import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    name: str
    type: str
    external_id: str | None
    timezone: str
    created_at: datetime
