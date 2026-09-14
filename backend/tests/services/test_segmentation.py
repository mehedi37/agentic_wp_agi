import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.segmentation import build_segments

TZ = ZoneInfo("Asia/Dhaka")


class _FakeMessage:
    def __init__(self, ts: datetime):
        self.id = uuid.uuid4()
        self.ts = ts


def test_single_segment_when_no_gap():
    base = datetime(2026, 1, 5, 9, 0, tzinfo=TZ)
    msgs = [_FakeMessage(base + timedelta(minutes=i * 5)) for i in range(10)]
    segments = build_segments(msgs, gap_minutes=45, max_messages=60)
    assert len(segments) == 1
    assert len(segments[0].message_ids) == 10


def test_splits_on_time_gap_over_threshold():
    base = datetime(2026, 1, 5, 9, 0, tzinfo=TZ)
    msgs = [
        _FakeMessage(base),
        _FakeMessage(base + timedelta(minutes=10)),
        _FakeMessage(base + timedelta(minutes=10, seconds=1) + timedelta(minutes=46)),
    ]
    segments = build_segments(msgs, gap_minutes=45, max_messages=60)
    assert len(segments) == 2
    assert len(segments[0].message_ids) == 2
    assert len(segments[1].message_ids) == 1


def test_gap_exactly_at_threshold_does_not_split():
    base = datetime(2026, 1, 5, 9, 0, tzinfo=TZ)
    msgs = [_FakeMessage(base), _FakeMessage(base + timedelta(minutes=45))]
    segments = build_segments(msgs, gap_minutes=45, max_messages=60)
    assert len(segments) == 1


def test_splits_on_max_message_count():
    base = datetime(2026, 1, 5, 9, 0, tzinfo=TZ)
    msgs = [_FakeMessage(base + timedelta(seconds=i)) for i in range(5)]
    segments = build_segments(msgs, gap_minutes=45, max_messages=2)
    assert [len(s.message_ids) for s in segments] == [2, 2, 1]


def test_empty_input_returns_empty_list():
    assert build_segments([], gap_minutes=45, max_messages=60) == []


def test_start_and_end_ts_match_first_last_message():
    base = datetime(2026, 1, 5, 9, 0, tzinfo=TZ)
    msgs = [_FakeMessage(base), _FakeMessage(base + timedelta(minutes=5))]
    segments = build_segments(msgs, gap_minutes=45, max_messages=60)
    assert segments[0].start_ts == msgs[0].ts
    assert segments[0].end_ts == msgs[1].ts
