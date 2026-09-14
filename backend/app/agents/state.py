import uuid
from typing import TypedDict

from app.schemas.item import ExtractedItem
from app.schemas.validation import ValidationReport


class PipelineState(TypedDict):
    run_id: str
    chat_id: uuid.UUID
    segment_id: uuid.UUID
    iteration: int
    candidate_items: list[ExtractedItem]
    validation: ValidationReport | None
    feedback: str | None
    status: str  # "in_progress" | "passed" | "needs_review"
