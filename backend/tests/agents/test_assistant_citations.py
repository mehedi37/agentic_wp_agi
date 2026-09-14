import uuid

from app.agents.assistant import valid_citations


def test_unknown_source_or_missing_citation_fails_validation():
    known, unknown = str(uuid.uuid4()), str(uuid.uuid4())
    sources = {known: {"text": "source"}}
    assert valid_citations(f"Supported [{known}]", sources)
    assert not valid_citations(f"Invented [{unknown}]", sources)
    assert not valid_citations("No citations", sources)
    assert not valid_citations(f"Mixed [{known}] [{unknown}]", sources)
