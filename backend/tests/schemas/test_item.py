import uuid

import pytest
from pydantic import ValidationError

from app.schemas.item import EvidenceRef, ExtractedItem


def test_extracted_item_valid() -> None:
    item = ExtractedItem(
        type="action",
        title="Send the invoice",
        evidence=[EvidenceRef(message_id=uuid.uuid4(), quote="please send the invoice")],
        confidence=0.87,
    )
    assert item.status_hint == "new"
    assert item.confidence == 0.87


def test_extracted_item_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        ExtractedItem(type="risk", title="Server may fail", confidence=1.5)
