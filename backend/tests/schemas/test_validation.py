from app.schemas.validation import ItemVerdict, ValidationIssue, ValidationReport


def test_validation_report_passed_with_no_issues() -> None:
    report = ValidationReport(passed=True)
    assert report.issues == []
    assert report.per_item_verdicts == []
    assert report.feedback is None


def test_validation_report_captures_failure_feedback() -> None:
    report = ValidationReport(
        passed=False,
        issues=[
            ValidationIssue(
                item_index=1,
                field="evidence",
                message="quote not found in msg 8841",
            ),
            ValidationIssue(
                item_index=1,
                field="owner_raw",
                message="owner 'Rafi bhai' ambiguous between 2 participants",
            ),
        ],
        per_item_verdicts=[
            ItemVerdict(item_index=0, passed=True, confidence=0.91),
            ItemVerdict(
                item_index=1,
                passed=False,
                confidence=0.3,
                issues=[
                    ValidationIssue(
                        item_index=1, field="evidence", message="quote not found in msg 8841"
                    )
                ],
            ),
        ],
        feedback="item 2: quote not found in msg 8841; owner 'Rafi bhai' ambiguous between 2 participants",
    )

    assert report.passed is False
    assert len(report.issues) == 2
    assert report.per_item_verdicts[0].passed is True
    assert report.per_item_verdicts[1].passed is False
    assert "quote not found" in (report.feedback or "")
