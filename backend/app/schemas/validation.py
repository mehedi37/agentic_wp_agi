from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    """One concrete problem the Validator agent found.

    `item_index` ties the issue back to a position in the Analyst's
    `list[ExtractedItem]` output (`None` means the issue is segment-level,
    not tied to a specific candidate item). `field` names the offending
    field (e.g. "evidence", "owner_raw", "due_at") when the issue is
    field-specific.
    """

    item_index: int | None = None
    field: str | None = None
    message: str


class ItemVerdict(BaseModel):
    """The Validator's per-item pass/fail verdict, per PLAN.md §6.3."""

    item_index: int
    passed: bool
    confidence: float | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """The Validator agent's output (PLAN.md §6.3): `{passed, issues[],
    per_item_verdicts}`, plus a human-readable `feedback` string that is fed
    back into the Analyst prompt on the next retry iteration, e.g. "item 2:
    quote not found in msg 8841; owner 'Rafi bhai' ambiguous between 2
    participants".
    """

    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    per_item_verdicts: list[ItemVerdict] = Field(default_factory=list)
    feedback: str | None = None
