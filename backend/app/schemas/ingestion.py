import uuid

from pydantic import BaseModel


class IngestResponse(BaseModel):
    job_id: uuid.UUID
    chat_id: uuid.UUID
    status: str
    inserted: int
    duplicates: int
    unparsed_lines: int
