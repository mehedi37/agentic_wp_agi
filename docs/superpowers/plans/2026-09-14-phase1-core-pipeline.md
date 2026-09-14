# Phase 1: Core Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 0 skeleton into a real, demonstrable pipeline: parse WhatsApp export files into canonical messages, generate a committed sample dataset with planted scenarios, group messages into segments and resolve dates/participants, write short- and long-term memory (embeddings + hybrid retrieval), and run the Analyst⇄Validator agent loop over a LangGraph pipeline graph so a batch of raw chat text becomes structured, evidence-cited items. This is the P0 core the whole project depends on — after this phase, running the pipeline on the sample data produces real `items` rows with evidence, which Phase 2's Monitor/Action/Assistant and Phase 3's dashboard read.

**Architecture:** Deterministic ingestion (parser + service) feeds canonical `Message` rows into Postgres and enqueues an ARQ job per chat batch. The ARQ worker runs a LangGraph `StateGraph`: `load_batch → segment → analyse ⇄ validate (retry ≤3) → memory_write → END`, with every node logged to `agent_runs`. The Analyst and Validator are LLM-provider-agnostic (use the Phase 0 `LLMProvider` interface — `FakeProvider` in tests, `AnthropicProvider`/`OllamaProvider` in real runs). Memory writes populate embeddings and a rolling per-chat summary; retrieval fuses pgvector cosine search with Postgres full-text search via Reciprocal Rank Fusion.

**Tech Stack:** Everything from Phase 0's Global Constraints, plus: LangGraph (`langgraph`) for the pipeline graph, PyYAML (`pyyaml`) for the sample-data storyline, `tzdata` (zoneinfo needs a tz database on slim Docker images). No new frontend dependencies this phase.

**Spec:** `PLAN.md` (repo root) — sections 4.1, 6.1–6.3, 7, 8, 10, 11, 13 (Phase 1 row). This plan also argues from the already-implemented Phase 0 contracts, read directly from the `implementation` branch: `backend/app/db/models.py`, `backend/app/schemas/{message,segment,item,validation,enums}.py`, `backend/app/llm/base.py`, `backend/app/llm/factory.py`, `backend/app/core/config.py`, `backend/app/api/deps.py`.

## Global Constraints

- No AI-attribution or AI-collaborator credit anywhere in this repository: never add "Co-Authored-By", "Generated with", a session/tool link, or similar credit lines in commit messages, PR descriptions, code comments, or docs. Commit messages are plain, describing only the change. This does NOT bar legitimately naming "Anthropic"/"Claude" as a configured LLM vendor.
- Backend package manager is **uv**; all backend commands run through `uv run ...`. Python version floor **3.12**.
- All backend code is typed; `mypy app` must pass with no errors. `ruff check .` (the whole `backend/` tree, not just `app/`) must pass with no errors — this was a real regression in Phase 0 (hidden because `make lint` only checked `app/`); `make lint` now checks the whole tree, keep it that way.
- Embedding dimension is **1024** everywhere (`settings.embedding_dim`, matches `bge-m3`). `EmbeddingProvider.embed(texts: list[str]) -> list[list[float]]` (see `app/llm/embeddings.py`) is the only way to get vectors — never call a provider's HTTP API directly from agent/service code.
- `LLMProvider` (see `app/llm/base.py`) is the only way to call an LLM: `chat(...)`, `structured(...)`, `tool_loop(...)`, obtained via `app.llm.factory.get_llm_provider(on_call=...)`. No task in this phase's automated tests calls a real external LLM API — tests use `FakeProvider` (`app.llm.fake_provider.FakeProvider`) exclusively, scripting `structured_responses`/`tool_loop_calls` as needed. A real Anthropic/Ollama call is allowed only behind a manual, skipped-by-default smoke test.
- Timezone for date logic is **Asia/Dhaka** (`settings.app_timezone`); store all timestamps as UTC (`TIMESTAMPTZ`) and convert to `Asia/Dhaka` only for display/relative-date resolution. Use `zoneinfo.ZoneInfo`, never a hardcoded offset.
- Two roles only: `manager` and `analyst`, exactly as Phase 0 implemented (`app/schemas/enums.py: Role`). Any new route in this phase that mutates data requires `Depends(require_role("manager", "analyst"))` at minimum; read-only routes require `Depends(get_current_user)`.
- Segmentation rule (this plan's ruling, see Task 3): a segment closes on a time gap over **45 minutes** or once it holds **60 messages**, whichever comes first. Deliberately deterministic — no LLM call in segmentation itself; topic coherence in practice comes from the time-gap rule, and the Analyst assigns `topic`/`category` per segment during extraction. Do not add a separate LLM-based topic-shift detector in this phase.
- Validator retry loop: **max 3 iterations** per segment (`iteration` 1, 2, 3). After iteration 3 still failing, or any iteration passing with overall confidence < 0.6, the segment's items are stored with `validation_status="needs_review"` and the graph proceeds (never loops forever, never drops the segment).
- Every `agent_runs` row this phase writes uses `agent` ∈ `{"pipeline"}` for now (Phase 2 adds `"monitor"`, `"action"`, `"assistant"`) and `node` ∈ `{"load_batch", "segment", "analyse", "validate", "memory_write"}`.
- Full-text search config is **`simple`**, not `english` (PLAN.md §7 requires `simple` specifically so Banglish/Bangla tokens are not mangled by English stemming). The Phase 0 migration used `english` by mistake — Task 4 of this plan corrects it with a new migration; do not edit the Phase 0 migration file itself.
- Sample data is fully deterministic and hand-authored (no LLM call in the default generation path) so the committed dataset and its gold labels are guaranteed exact — never regenerated with different content between runs. This plan's Task 2 storyline covers a smaller-but-complete slice of PLAN.md §11 (see Task 2's own note) rather than the full 2,500-message/8-week scale; every planted scenario and both export formats are still represented, and it is committed so the demo never needs regeneration.
- New third-party dependencies land in `backend/pyproject.toml` `[project.dependencies]` (never installed ad hoc); after editing, run `uv lock` and commit the updated `uv.lock`.

---

## File Structure

```
backend/
├── app/
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── export_parser/
│   │       ├── __init__.py
│   │       ├── types.py          # ParsedMessage dataclass
│   │       ├── detect.py         # detect_format()
│   │       ├── datetime_parse.py # parse_export_datetime()
│   │       ├── android.py        # parse_android()
│   │       ├── ios.py            # parse_ios()
│   │       └── zip_loader.py     # load_export_bytes()
│   ├── services/
│   │   ├── participants.py       # get_or_create_participant() [T1.1], resolve_participant() [T1.3]
│   │   ├── ingestion.py          # ingest_export() [T1.1]
│   │   ├── segmentation.py       # build_segments(), persist_pending_segments() [T1.3]
│   │   └── date_resolver.py      # resolve_date() [T1.3]
│   ├── schemas/
│   │   └── ingestion.py          # IngestResponse [T1.1]
│   ├── api/routes/
│   │   └── ingest.py             # POST /api/ingest/upload [T1.1]
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py         # ChatState read/update [T1.4]
│   │   ├── long_term.py          # embed_and_store_*() [T1.4]
│   │   └── retrieval.py          # hybrid_search() with RRF [T1.4]
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py              # PipelineState TypedDict [T1.5]
│   │   ├── prompts/
│   │   │   ├── analyst_system.md
│   │   │   └── validator_judge_system.md
│   │   ├── analyst.py            # run_analyst() [T1.5]
│   │   ├── validator.py          # run_validator() [T1.5]
│   │   ├── agent_runs.py         # log_agent_run() helper [T1.5]
│   │   └── pipeline_graph.py     # build_pipeline_graph() [T1.5]
│   └── workers/
│       ├── __init__.py
│       ├── queue.py               # enqueue_process_batch() [T1.1]
│       ├── settings.py            # ARQ WorkerSettings [T1.5]
│       └── jobs.py                # process_batch() [T1.5]
├── alembic/versions/
│   ├── 0003_chat_state.py         # [T1.4]
│   └── 0004_fts_simple_config.py  # [T1.4]
├── tests/
│   ├── ingestion/
│   │   ├── test_detect.py
│   │   ├── test_android_parser.py
│   │   ├── test_ios_parser.py
│   │   ├── test_zip_loader.py
│   │   └── test_datetime_parse.py
│   ├── services/
│   │   ├── test_ingestion_service.py
│   │   ├── test_segmentation.py
│   │   ├── test_date_resolver.py
│   │   └── test_participants.py
│   ├── memory/
│   │   ├── test_short_term.py
│   │   ├── test_long_term.py
│   │   └── test_retrieval.py
│   ├── agents/
│   │   ├── test_analyst.py
│   │   ├── test_validator.py
│   │   └── test_pipeline_graph.py
│   └── api/
│       └── test_ingest.py
scripts/
├── sample_storyline.yaml          # [T1.2]
└── generate_sample_data.py        # [T1.2]
data/sample/
├── exports/                       # generated + committed [T1.2]
├── webhook_fixtures/              # empty this phase (Phase 4)
└── gold/                          # generated + committed [T1.2]
```

---

### Task 1: Export Parser + Ingestion Service + Upload API

**Files:**
- Create: `backend/app/ingestion/__init__.py`, `backend/app/ingestion/export_parser/__init__.py`, `backend/app/ingestion/export_parser/types.py`, `backend/app/ingestion/export_parser/detect.py`, `backend/app/ingestion/export_parser/datetime_parse.py`, `backend/app/ingestion/export_parser/android.py`, `backend/app/ingestion/export_parser/ios.py`, `backend/app/ingestion/export_parser/zip_loader.py`
- Create: `backend/app/services/participants.py`, `backend/app/services/ingestion.py`
- Create: `backend/app/schemas/ingestion.py`
- Create: `backend/app/api/routes/ingest.py`
- Create: `backend/app/workers/__init__.py`, `backend/app/workers/queue.py`
- Modify: `backend/app/main.py` (register the new router)
- Modify: `backend/pyproject.toml` (add `tzdata`)
- Test: `backend/tests/ingestion/test_detect.py`, `test_android_parser.py`, `test_ios_parser.py`, `test_zip_loader.py`, `test_datetime_parse.py`, `backend/tests/services/test_ingestion_service.py`, `test_participants.py`, `backend/tests/api/test_ingest.py`

**Interfaces:**
- Consumes: `app.db.models.{Chat, Participant, Message, IngestionJob}`, `app.db.session.get_session`, `app.api.deps.{get_current_user, require_role}`, `app.schemas.enums.Role`.
- Produces (for later tasks): `ParsedMessage` dataclass (Task 3/4/5 read `Message` rows this task writes, not `ParsedMessage` directly — it's an internal parse-stage type). `get_or_create_participant(session, chat_id, display_name) -> Participant` in `app/services/participants.py` — Task 3 imports and extends this same module. `enqueue_process_batch(chat_id: uuid.UUID) -> Awaitable[None]` in `app/workers/queue.py` — Task 5's ARQ `WorkerSettings` registers the `"process_batch"` job name this function enqueues by string, so there is no import-time coupling between Task 1 and Task 5.

Every export line may carry WhatsApp's invisible marks: `‎` (left-to-right mark, common before sender names and in system lines) and ` ` (narrow no-break space, common between time and AM/PM on iOS). Strip `‎` entirely and replace ` ` with a regular space before any regex match, in every parser.

- [ ] **Step 1: `ParsedMessage` type and format detection — write the failing tests**

`backend/tests/ingestion/test_detect.py`:
```python
from app.ingestion.export_parser.detect import detect_format

def test_detects_android():
    text = "12/03/2026, 9:41 AM - Rafi: kal delivery hobe\n12/03/2026, 9:42 AM - Nadia: ok"
    assert detect_format(text) == "android"

def test_detects_ios():
    text = "[12/03/2026, 09:41:03] Rafi: kal delivery hobe\n[12/03/2026, 09:42:11] Nadia: ok"
    assert detect_format(text) == "ios"

def test_detects_android_with_invisible_marks():
    text = "‎12/03/2026, 9:41 AM - Rafi: hi"
    assert detect_format(text) == "android"

def test_unrecognized_raises():
    import pytest
    from app.ingestion.export_parser.detect import UnrecognizedFormatError
    with pytest.raises(UnrecognizedFormatError):
        detect_format("this is not a whatsapp export at all")
```

- [ ] **Step 2: run tests, confirm failure (`ModuleNotFoundError`)**

Run: `cd backend && uv run pytest tests/ingestion/test_detect.py -v`
Expected: FAIL — `app.ingestion` does not exist yet.

- [ ] **Step 3: implement `types.py` and `detect.py`**

`backend/app/ingestion/export_parser/types.py`:
```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedMessage:
    ts: datetime  # tz-aware, in the chat's timezone
    sender: str | None  # None for system messages
    text: str
    is_system: bool
    media_type: str | None  # "image" | "video" | "audio" | "document" | "sticker" | "gif" | None
    line_no: int  # 1-based line where this message started, for unparsed-line reporting


def strip_invisible_marks(text: str) -> str:
    return text.replace("‎", "").replace(" ", " ")
```

`backend/app/ingestion/export_parser/detect.py`:
```python
import re

from app.ingestion.export_parser.types import strip_invisible_marks

_ANDROID_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}(\s?[APap][Mm])?\s-\s")
_IOS_RE = re.compile(r"^\[\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}:\d{2}(\s?[APap][Mm])?\]\s")


class UnrecognizedFormatError(ValueError):
    pass


def detect_format(text: str) -> str:
    for raw_line in text.splitlines():
        line = strip_invisible_marks(raw_line).strip()
        if not line:
            continue
        if _IOS_RE.match(line):
            return "ios"
        if _ANDROID_RE.match(line):
            return "android"
        raise UnrecognizedFormatError(f"first non-empty line does not match any known export format: {line!r}")
    raise UnrecognizedFormatError("empty export text")
```

- [ ] **Step 4: run tests, confirm pass**

Run: `cd backend && uv run pytest tests/ingestion/test_detect.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: date/time parsing — write the failing tests**

`backend/tests/ingestion/test_datetime_parse.py`:
```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.ingestion.export_parser.datetime_parse import parse_export_datetime


TZ = "Asia/Dhaka"


def test_dmy_24h():
    dt = parse_export_datetime("12/03/2026", "14:30", date_order="DMY", tz=TZ)
    assert dt == datetime(2026, 3, 12, 14, 30, tzinfo=ZoneInfo(TZ))


def test_mdy_12h_pm():
    dt = parse_export_datetime("3/12/2026", "2:30 PM", date_order="MDY", tz=TZ)
    assert dt == datetime(2026, 3, 12, 14, 30, tzinfo=ZoneInfo(TZ))


def test_12h_with_seconds():
    dt = parse_export_datetime("12/03/26", "09:41:03 AM", date_order="DMY", tz=TZ)
    assert dt == datetime(2026, 3, 12, 9, 41, 3, tzinfo=ZoneInfo(TZ))


def test_2digit_year_pivots_to_2000s():
    dt = parse_export_datetime("1/1/24", "00:00", date_order="DMY", tz=TZ)
    assert dt.year == 2024


def test_unambiguous_day_over_12_overrides_configured_order():
    # 25 cannot be a month: must be day=25 regardless of date_order="MDY"
    dt = parse_export_datetime("25/03/2026", "10:00", date_order="MDY", tz=TZ)
    assert (dt.day, dt.month) == (25, 3)


def test_noon_and_midnight_12h():
    assert parse_export_datetime("1/1/2026", "12:00 AM", date_order="DMY", tz=TZ).hour == 0
    assert parse_export_datetime("1/1/2026", "12:00 PM", date_order="DMY", tz=TZ).hour == 12


def test_invalid_raises():
    with pytest.raises(ValueError):
        parse_export_datetime("31/02/2026", "10:00", date_order="DMY", tz=TZ)
```

- [ ] **Step 6: run, confirm failure; implement `datetime_parse.py`; run, confirm pass**

```python
import re
from datetime import datetime
from zoneinfo import ZoneInfo

_TIME_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2})(:(?P<s>\d{2}))?\s?(?P<ampm>[APap][Mm])?$"
)


def _pivot_year(year: int) -> int:
    return 2000 + year if year < 100 else year


def parse_export_datetime(date_str: str, time_str: str, *, date_order: str, tz: str) -> datetime:
    """`date_order` is "DMY" or "MDY" and is only a tie-breaker: if one part
    of the date is unambiguously > 12 it is treated as the day regardless
    of the configured order (handles exports where the configured order
    was guessed wrong but the data itself resolves the ambiguity)."""
    d1_str, d2_str, y_str = date_str.split("/")
    d1, d2, year = int(d1_str), int(d2_str), _pivot_year(int(y_str))

    if d1 > 12 and d2 <= 12:
        day, month = d1, d2
    elif d2 > 12 and d1 <= 12:
        day, month = d2, d1
    elif date_order == "MDY":
        month, day = d1, d2
    else:
        day, month = d1, d2

    m = _TIME_RE.match(time_str.strip())
    if not m:
        raise ValueError(f"unrecognized time: {time_str!r}")
    hour, minute = int(m.group("h")), int(m.group("m"))
    second = int(m.group("s") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm == "am":
        hour = 0 if hour == 12 else hour
    elif ampm == "pm":
        hour = 12 if hour == 12 else hour + 12

    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(tz))
```

Run: `cd backend && uv run pytest tests/ingestion/test_datetime_parse.py -v` — Expected: PASS (7 tests). `test_invalid_raises` passes because `datetime(2026, 2, 31, ...)` raises `ValueError` itself (Python's `datetime` validates the calendar).

- [ ] **Step 7: Android parser — write the failing tests**

`backend/tests/ingestion/test_android_parser.py`:
```python
from app.ingestion.export_parser.android import parse_android

TZ = "Asia/Dhaka"


def test_basic_two_messages():
    text = (
        "12/03/2026, 9:41 AM - Rafi: kal warehouse e jabo\n"
        "12/03/2026, 9:42 AM - Nadia: ok, notun update din"
    )
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
    assert msgs[0].sender == "Rafi" and msgs[0].text == "kal warehouse e jabo"
    assert msgs[1].sender == "Nadia" and not msgs[1].is_system


def test_multiline_message_appends_to_previous():
    text = (
        "12/03/2026, 9:41 AM - Rafi: line one\n"
        "line two continues\n"
        "line three continues\n"
        "12/03/2026, 9:42 AM - Nadia: separate message"
    )
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
    assert msgs[0].text == "line one\nline two continues\nline three continues"


def test_system_message_has_no_sender():
    text = "12/03/2026, 9:00 AM - Messages and calls are end-to-end encrypted."
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert msgs[0].sender is None and msgs[0].is_system is True


def test_media_omitted():
    text = "12/03/2026, 9:41 AM - Rafi: <Media omitted>"
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert msgs[0].media_type == "unknown" and msgs[0].text == ""


def test_invisible_marks_stripped():
    text = "‎12/03/2026, 9:41 AM - ‎Rafi: hello"
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert msgs[0].sender == "Rafi" and msgs[0].text == "hello"


def test_blank_lines_ignored():
    text = "12/03/2026, 9:41 AM - Rafi: hi\n\n\n12/03/2026, 9:42 AM - Nadia: hey"
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
```

- [ ] **Step 8: run, confirm failure; implement `android.py`; run, confirm pass**

```python
import re

from app.ingestion.export_parser.datetime_parse import parse_export_datetime
from app.ingestion.export_parser.types import ParsedMessage, strip_invisible_marks

_LINE_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s(?P<time>\d{1,2}:\d{2}(\s?[APap][Mm])?)\s-\s"
    r"((?P<sender>[^:]+):\s)?(?P<text>.*)$"
)
_MEDIA_OMITTED_RE = re.compile(r"^<Media omitted>$", re.IGNORECASE)


def parse_android(text: str, *, date_order: str, tz: str) -> list[ParsedMessage]:
    messages: list[ParsedMessage] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_invisible_marks(raw_line)
        if not line.strip():
            continue
        m = _LINE_RE.match(line)
        if m is None:
            if messages:
                messages[-1].text += "\n" + line
            continue
        ts = parse_export_datetime(m.group("date"), m.group("time"), date_order=date_order, tz=tz)
        sender = m.group("sender")
        body = m.group("text")
        is_media = bool(_MEDIA_OMITTED_RE.match(body.strip()))
        messages.append(
            ParsedMessage(
                ts=ts,
                sender=sender,
                text="" if is_media else body,
                is_system=sender is None,
                media_type="unknown" if is_media else None,
                line_no=line_no,
            )
        )
    return messages
```

Run: `cd backend && uv run pytest tests/ingestion/test_android_parser.py -v` — Expected: PASS (6 tests).

- [ ] **Step 9: iOS parser — write the failing tests, then implement, then verify**

`backend/tests/ingestion/test_ios_parser.py` (mirror the Android tests, iOS format):
```python
from app.ingestion.export_parser.ios import parse_ios

TZ = "Asia/Dhaka"


def test_basic_two_messages():
    text = (
        "[12/03/2026, 09:41:03] Rafi: kal warehouse e jabo\n"
        "[12/03/2026, 09:42:11] Nadia: ok, notun update din"
    )
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
    assert msgs[0].sender == "Rafi"


def test_multiline_message_appends_to_previous():
    text = (
        "[12/03/2026, 09:41:03] Rafi: line one\n"
        "line two continues\n"
        "[12/03/2026, 09:42:11] Nadia: separate"
    )
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert msgs[0].text == "line one\nline two continues"


def test_system_message_has_no_sender():
    text = "[12/03/2026, 09:00:00] Messages and calls are end-to-end encrypted."
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert msgs[0].sender is None and msgs[0].is_system is True


def test_media_omitted_variants():
    text = (
        "[12/03/2026, 09:41:03] Rafi: image omitted\n"
        "[12/03/2026, 09:42:00] Nadia: video omitted\n"
        "[12/03/2026, 09:43:00] Rafi: ‎document omitted"
    )
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert [m.media_type for m in msgs] == ["image", "video", "document"]


def test_12h_am_pm_variant():
    text = "[3/12/26, 9:41:03 AM] Rafi: hi"
    msgs = parse_ios(text, date_order="MDY", tz=TZ)
    assert msgs[0].ts.hour == 9
```

`backend/app/ingestion/export_parser/ios.py`:
```python
import re

from app.ingestion.export_parser.datetime_parse import parse_export_datetime
from app.ingestion.export_parser.types import ParsedMessage, strip_invisible_marks

_LINE_RE = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s(?P<time>\d{1,2}:\d{2}:\d{2}(\s?[APap][Mm])?)\]\s"
    r"((?P<sender>[^:]+):\s)?(?P<text>.*)$"
)
_MEDIA_RE = re.compile(r"^(image|video|audio|document|sticker|gif|GIF) omitted$", re.IGNORECASE)


def parse_ios(text: str, *, date_order: str, tz: str) -> list[ParsedMessage]:
    messages: list[ParsedMessage] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_invisible_marks(raw_line)
        if not line.strip():
            continue
        m = _LINE_RE.match(line)
        if m is None:
            if messages:
                messages[-1].text += "\n" + line
            continue
        ts = parse_export_datetime(m.group("date"), m.group("time"), date_order=date_order, tz=tz)
        sender = m.group("sender")
        body = m.group("text")
        media_m = _MEDIA_RE.match(body.strip())
        messages.append(
            ParsedMessage(
                ts=ts,
                sender=sender,
                text="" if media_m else body,
                is_system=sender is None,
                media_type=media_m.group(1).lower() if media_m else None,
                line_no=line_no,
            )
        )
    return messages
```

Run: `cd backend && uv run pytest tests/ingestion/test_ios_parser.py -v` — Expected: PASS (5 tests).

- [ ] **Step 10: zip loader — write the failing tests, then implement**

`backend/tests/ingestion/test_zip_loader.py`:
```python
import io
import zipfile

from app.ingestion.export_parser.zip_loader import load_export_bytes


def _make_zip(chat_txt: bytes, extra_files: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("_chat.txt", chat_txt)
        for name, content in (extra_files or {}).items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_plain_txt_bytes_returned_as_is():
    text, media_names = load_export_bytes(b"12/03/2026, 9:41 AM - Rafi: hi", filename="chat.txt")
    assert text == "12/03/2026, 9:41 AM - Rafi: hi"
    assert media_names == []


def test_zip_extracts_chat_txt_and_lists_media():
    zip_bytes = _make_zip(
        b"12/03/2026, 9:41 AM - Rafi: hi\n12/03/2026, 9:42 AM - Rafi: <Media omitted>",
        extra_files={"IMG-20260312-WA0001.jpg": b"\xff\xd8\xff"},
    )
    text, media_names = load_export_bytes(zip_bytes, filename="chat_export.zip")
    assert "Rafi: hi" in text
    assert media_names == ["IMG-20260312-WA0001.jpg"]


def test_zip_without_chat_txt_raises():
    import pytest

    from app.ingestion.export_parser.zip_loader import NoChatFileError

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"not a chat export")
    with pytest.raises(NoChatFileError):
        load_export_bytes(buf.getvalue(), filename="bad.zip")
```

`backend/app/ingestion/export_parser/zip_loader.py`:
```python
import io
import zipfile


class NoChatFileError(ValueError):
    pass


def load_export_bytes(file_bytes: bytes, *, filename: str) -> tuple[str, list[str]]:
    """Returns (chat_text, media_filenames). `media_filenames` lists names
    only -- media content is never stored (PLAN.md §10: media is metadata
    only)."""
    if filename.lower().endswith(".zip") or file_bytes[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            chat_name = next(
                (n for n in zf.namelist() if n.lower().endswith("_chat.txt") or n.lower() == "_chat.txt"),
                None,
            )
            if chat_name is None:
                raise NoChatFileError(f"no _chat.txt found in {filename}")
            chat_text = zf.read(chat_name).decode("utf-8", errors="replace")
            media_names = sorted(n for n in zf.namelist() if n != chat_name and not n.endswith("/"))
            return chat_text, media_names
    return file_bytes.decode("utf-8", errors="replace"), []
```

Run: `cd backend && uv run pytest tests/ingestion/test_zip_loader.py -v` — Expected: PASS (3 tests).

- [ ] **Step 11: participants service — write the failing test, implement, verify**

`backend/tests/services/test_participants.py` — write against a real test-DB session (see `backend/tests/services/test_audit.py` from Phase 0 for the exact fixture pattern this repo uses; reuse the same `db_session` fixture, do not invent a new one):
```python
from app.services.participants import get_or_create_participant


def test_creates_new_participant(db_session, seed_chat):
    p = get_or_create_participant(db_session, seed_chat.id, "Rafi")
    db_session.flush()
    assert p.display_name == "Rafi"
    assert p.chat_id == seed_chat.id


def test_returns_existing_participant_case_insensitive(db_session, seed_chat):
    p1 = get_or_create_participant(db_session, seed_chat.id, "Rafi")
    db_session.flush()
    p2 = get_or_create_participant(db_session, seed_chat.id, "rafi")
    assert p1.id == p2.id


def test_same_name_different_chats_are_different_participants(db_session, seed_chat, seed_chat_2):
    p1 = get_or_create_participant(db_session, seed_chat.id, "Rafi")
    p2 = get_or_create_participant(db_session, seed_chat_2.id, "Rafi")
    db_session.flush()
    assert p1.id != p2.id
```

If `backend/tests/services/test_audit.py` does not already have `db_session`/`seed_chat` fixtures at a shared `conftest.py`, add a `backend/tests/services/conftest.py` with:
```python
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models import Chat


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def seed_chat(db_session):
    chat = Chat(source="export", name="Test Chat", type="group", timezone="Asia/Dhaka")
    db_session.add(chat)
    db_session.flush()
    return chat


@pytest.fixture()
def seed_chat_2(db_session):
    chat = Chat(source="export", name="Test Chat 2", type="group", timezone="Asia/Dhaka")
    db_session.add(chat)
    db_session.flush()
    return chat
```
(These tests need a real Postgres reachable at `settings.database_url` with migrations applied — same as every other DB-touching test in this repo. If `backend/tests/services/test_audit.py` already defines equivalent fixtures, reuse them instead of duplicating — read that file first.)

`backend/app/services/participants.py`:
```python
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Participant


def get_or_create_participant(session: Session, chat_id: uuid.UUID, display_name: str) -> Participant:
    existing = session.scalar(
        select(Participant).where(
            Participant.chat_id == chat_id,
            func.lower(Participant.display_name) == display_name.strip().lower(),
        )
    )
    if existing is not None:
        return existing
    participant = Participant(chat_id=chat_id, display_name=display_name.strip())
    session.add(participant)
    session.flush()
    return participant
```

Run: `cd backend && uv run pytest tests/services/test_participants.py -v` — Expected: PASS (3 tests, against the real DB — start it if needed: `cd .. && docker compose up -d postgres && make migrate`).

- [ ] **Step 12: ARQ enqueue stub — write the failing test, implement, verify**

`backend/app/workers/__init__.py`: empty.

`backend/app/workers/queue.py`:
```python
import uuid

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_process_batch(chat_id: uuid.UUID) -> None:
    """Enqueues the `"process_batch"` ARQ job by name. The job function
    itself is registered later (Task 5's `app.workers.settings.WorkerSettings`)
    -- enqueueing by string name means this module never imports Task 5's
    code, so Task 1 has no forward dependency on it."""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("process_batch", str(chat_id))
    finally:
        await pool.close()
```

No dedicated unit test for this stub (it requires a live Redis and has three lines of real logic) — Step 14's ingestion-service test verifies it is *called* via monkeypatching, which is the meaningful check. Do not write a separate test file for `queue.py` alone.

- [ ] **Step 13: ingestion schema — implement (no dedicated test; covered by Step 15's API test)**

`backend/app/schemas/ingestion.py`:
```python
import uuid

from pydantic import BaseModel


class IngestResponse(BaseModel):
    job_id: uuid.UUID
    chat_id: uuid.UUID
    status: str
    inserted: int
    duplicates: int
    unparsed_lines: int
```

- [ ] **Step 14: ingestion service — write the failing tests**

`backend/tests/services/test_ingestion_service.py`:
```python
import hashlib
from unittest.mock import AsyncMock

from app.db.models import Message
from app.services.ingestion import ingest_export


def _content_hash(chat_id, ts, sender, text) -> str:
    return hashlib.sha256(f"{chat_id}|{ts.isoformat()}|{sender}|{text}".encode()).hexdigest()


async def test_ingests_new_android_export(db_session, seed_chat):
    text = (
        "12/03/2026, 9:41 AM - Rafi: kal delivery hobe\n"
        "12/03/2026, 9:42 AM - Nadia: ok thik ache"
    )
    enqueue = AsyncMock()
    stats = await ingest_export(
        db_session,
        chat_id=seed_chat.id,
        filename="chat.txt",
        file_bytes=text.encode(),
        date_order="DMY",
        enqueue=enqueue,
    )
    db_session.commit()
    assert stats.inserted == 2
    assert stats.duplicates == 0
    rows = db_session.query(Message).filter(Message.chat_id == seed_chat.id).all()
    assert len(rows) == 2
    enqueue.assert_awaited_once_with(seed_chat.id)


async def test_reupload_is_idempotent(db_session, seed_chat):
    text = "12/03/2026, 9:41 AM - Rafi: kal delivery hobe"
    enqueue = AsyncMock()
    await ingest_export(
        db_session, chat_id=seed_chat.id, filename="chat.txt", file_bytes=text.encode(),
        date_order="DMY", enqueue=enqueue,
    )
    db_session.commit()
    stats2 = await ingest_export(
        db_session, chat_id=seed_chat.id, filename="chat.txt", file_bytes=text.encode(),
        date_order="DMY", enqueue=enqueue,
    )
    db_session.commit()
    assert stats2.inserted == 0
    assert stats2.duplicates == 1
    rows = db_session.query(Message).filter(Message.chat_id == seed_chat.id).all()
    assert len(rows) == 1


async def test_participants_created_from_senders(db_session, seed_chat):
    text = "12/03/2026, 9:41 AM - Rafi: hi\n12/03/2026, 9:42 AM - Nadia: hey"
    enqueue = AsyncMock()
    await ingest_export(
        db_session, chat_id=seed_chat.id, filename="chat.txt", file_bytes=text.encode(),
        date_order="DMY", enqueue=enqueue,
    )
    db_session.commit()
    from app.db.models import Participant
    names = {p.display_name for p in db_session.query(Participant).filter(Participant.chat_id == seed_chat.id)}
    assert names == {"Rafi", "Nadia"}
```

- [ ] **Step 15: implement `services/ingestion.py`, verify**

```python
import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionJob, Message
from app.ingestion.export_parser.android import parse_android
from app.ingestion.export_parser.detect import detect_format
from app.ingestion.export_parser.ios import parse_ios
from app.ingestion.export_parser.types import ParsedMessage
from app.ingestion.export_parser.zip_loader import load_export_bytes
from app.services.participants import get_or_create_participant


@dataclass
class IngestStats:
    job: IngestionJob
    inserted: int
    duplicates: int
    unparsed_lines: int


def _content_hash(chat_id: uuid.UUID, msg: ParsedMessage) -> str:
    return hashlib.sha256(f"{chat_id}|{msg.ts.isoformat()}|{msg.sender}|{msg.text}".encode()).hexdigest()


async def ingest_export(
    session: Session,
    *,
    chat_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
    date_order: str = "DMY",
    tz: str = "Asia/Dhaka",
    enqueue: Callable[[uuid.UUID], Awaitable[None]] | None = None,
) -> IngestStats:
    job = IngestionJob(source="export", filename=filename, status="processing")
    session.add(job)
    session.flush()

    chat_text, _media_names = load_export_bytes(file_bytes, filename=filename)
    fmt = detect_format(chat_text)
    parsed = parse_android(chat_text, date_order=date_order, tz=tz) if fmt == "android" \
        else parse_ios(chat_text, date_order=date_order, tz=tz)

    inserted = 0
    duplicates = 0
    for msg in parsed:
        content_hash = _content_hash(chat_id, msg)
        exists = session.scalar(select(Message.id).where(Message.content_hash == content_hash))
        if exists is not None:
            duplicates += 1
            continue
        participant = None
        if msg.sender is not None:
            participant = get_or_create_participant(session, chat_id, msg.sender)
        session.add(
            Message(
                chat_id=chat_id,
                participant_id=participant.id if participant else None,
                ts=msg.ts,
                text=msg.text,
                media_type=msg.media_type,
                is_system=msg.is_system,
                content_hash=content_hash,
            )
        )
        inserted += 1

    job.status = "completed"
    job.stats = {"inserted": inserted, "duplicates": duplicates, "unparsed_lines": 0}
    session.flush()

    if enqueue is not None and inserted > 0:
        await enqueue(chat_id)

    return IngestStats(job=job, inserted=inserted, duplicates=duplicates, unparsed_lines=0)
```

Run: `cd backend && uv run pytest tests/services/test_ingestion_service.py -v` — Expected: PASS (3 tests).

- [ ] **Step 16: upload API — write the failing test**

`backend/tests/api/test_ingest.py` (follow the auth pattern from `backend/tests/api/test_deps.py` — read it first for how this repo gets an authenticated `TestClient`):
```python
import io

from app.db.models import Chat


def test_upload_creates_chat_and_ingests(client, analyst_token, db_session):
    text = "12/03/2026, 9:41 AM - Rafi: kal delivery hobe"
    resp = client.post(
        "/api/ingest/upload",
        headers={"Authorization": f"Bearer {analyst_token}"},
        data={"chat_name": "New Chat", "date_order": "DMY"},
        files={"file": ("chat.txt", io.BytesIO(text.encode()), "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    chat = db_session.get(Chat, body["chat_id"])
    assert chat.name == "New Chat" and chat.source == "export"


def test_upload_requires_auth(client):
    resp = client.post("/api/ingest/upload", files={"file": ("chat.txt", io.BytesIO(b""), "text/plain")})
    assert resp.status_code == 401


def test_upload_bad_zip_returns_422(client, analyst_token):
    resp = client.post(
        "/api/ingest/upload",
        headers={"Authorization": f"Bearer {analyst_token}"},
        data={"chat_name": "Bad"},
        files={"file": ("chat.zip", io.BytesIO(b"not a zip"), "application/zip")},
    )
    assert resp.status_code == 422
```
If `analyst_token` is not already a fixture in this repo's API test suite, add it to `backend/tests/api/conftest.py` (check first — Phase 0's auth tests likely already need one) by seeding a user and calling `create_access_token` directly, matching however `backend/tests/api/test_deps.py` already does it.

- [ ] **Step 17: implement the route, register it, verify**

`backend/app/api/routes/ingest.py`:
```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.models import Chat
from app.db.session import get_session
from app.ingestion.export_parser.detect import UnrecognizedFormatError
from app.ingestion.export_parser.zip_loader import NoChatFileError
from app.schemas.auth import CurrentUser
from app.schemas.ingestion import IngestResponse
from app.services.ingestion import ingest_export
from app.workers.queue import enqueue_process_batch

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/upload", response_model=IngestResponse)
async def upload_export(
    file: UploadFile = File(...),
    chat_name: str = Form(...),
    date_order: str = Form("DMY"),
    _user: CurrentUser = Depends(require_role("analyst", "manager")),
    session: Session = Depends(get_session),
) -> IngestResponse:
    chat = Chat(source="export", name=chat_name, type="group", timezone="Asia/Dhaka")
    session.add(chat)
    session.flush()

    file_bytes = await file.read()
    try:
        stats = await ingest_export(
            session,
            chat_id=chat.id,
            filename=file.filename or "upload",
            file_bytes=file_bytes,
            date_order=date_order,
            enqueue=enqueue_process_batch,
        )
    except (UnrecognizedFormatError, NoChatFileError) as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    session.commit()
    return IngestResponse(
        job_id=stats.job.id,
        chat_id=chat.id,
        status=stats.job.status,
        inserted=stats.inserted,
        duplicates=stats.duplicates,
        unparsed_lines=stats.unparsed_lines,
    )
```

In `backend/app/main.py`, add:
```python
from app.api.routes import ingest
...
app.include_router(ingest.router, prefix="/api")
```

Run: `cd backend && uv run pytest tests/api/test_ingest.py -v` — Expected: PASS (3 tests). The route calls `enqueue_process_batch`, which needs Redis reachable — if `test_upload_creates_chat_and_ingests` fails only on the enqueue step in an environment with no Redis running, start it (`docker compose up -d redis`) rather than mocking `enqueue_process_batch` in the API test — this is meant to be a real end-to-end check.

- [ ] **Step 18: add `tzdata`, whole-task verification, commit**

In `backend/pyproject.toml`, add `"tzdata>=2024.2"` to `[project.dependencies]`. Then:
```bash
cd backend
uv lock
uv sync
uv run ruff check .
uv run mypy app
uv run pytest -q
```
All must pass with zero errors/failures. Then:
```bash
git add backend/app/ingestion backend/app/services/participants.py backend/app/services/ingestion.py \
  backend/app/schemas/ingestion.py backend/app/api/routes/ingest.py backend/app/workers \
  backend/app/main.py backend/pyproject.toml backend/uv.lock backend/tests/ingestion \
  backend/tests/services/test_ingestion_service.py backend/tests/services/test_participants.py \
  backend/tests/services/conftest.py backend/tests/api/test_ingest.py
git commit -m "feat: add export parser, ingestion service, and upload API"
```

---

### Task 2: Sample Data Generator + Sample Exports + Gold Labels

**Files:**
- Create: `scripts/sample_storyline.yaml`
- Create: `scripts/generate_sample_data.py`
- Create: `data/sample/exports/` (generated, committed)
- Create: `data/sample/gold/` (generated, committed)
- Test: `backend/tests/scripts/test_generate_sample_data.py`

**Interfaces:**
- Consumes: Task 1's `parse_android`/`parse_ios`/`detect_format` (this task's acceptance test parses its own output back through them).
- Produces: `data/sample/exports/*.txt` and `*.zip` (committed), `data/sample/gold/*.json` (committed) — Task 5's manual/eval run reads these; Phase 4's `evals/` harness (out of scope this phase) reads the gold files too, so the gold JSON schema below is final, not provisional.

**Scope note (this plan's ruling, see Global Constraints):** PLAN.md §11 describes 5 chats, ~2,500 messages, ~8 weeks. This task delivers the same 5 chats, the same planted-scenario list, both export formats, and the same multilingual mix, but at a smaller scale (roughly 30–45 messages per chat, spanning about 2–3 simulated weeks) so the dataset is fully hand-authored and deterministic rather than partially LLM-generated. This is a deliberate scope reduction to ship a correct, demonstrable Phase 1 fast — every capability the brief asks to see demonstrated is still present. If a larger dataset is wanted later, extend `sample_storyline.yaml` with more entries following the same schema; nothing else needs to change.

**Storyline schema** (`scripts/sample_storyline.yaml`):
```yaml
org: "Nodi Logistics Ltd (fictional)"
chats:
  - key: management_team
    name: "Management Team"
    type: group
    export_format: android   # "android" or "ios" -> which renderer + which committed file extension
    date_order: DMY
    participants: ["Kamal (MD)", "Farah (Ops Head)", "Rafi (Warehouse Lead)"]
    messages:
      - day: 0
        time: "09:15"
        sender: "Kamal (MD)"
        text: "Team, decision: we are moving the Padma warehouse rollout to Q2. Confirmed in yesterday's board call."
      - day: 0
        time: "09:17"
        sender: "Farah (Ops Head)"
        text: "Noted, will update the project plan."
      - day: 6
        time: "10:02"
        sender: "Kamal (MD)"
        text: "Reversing that -- board wants Padma rollout back on the original Q1 timeline after all. Sorry for the churn."
        planted_scenario: reversed_decision
        gold:
          type: decision
          title: "Padma warehouse rollout timeline reversed back to Q1"
          status_hint: update
          related_item_title: "Padma warehouse rollout moved to Q2"
```
Every message entry: `day` (int, offset from a fixed anchor date `2026-01-05`), `time` (`HH:MM`, 24h), `sender` (must match a name in `participants`, or omit `sender` for a system message and set `system: true`), `text`. A message that plants a required scenario adds `planted_scenario: <tag>` and a `gold:` block describing the expected extracted item (`type`, `title`, `owner_raw` (optional), `due_date_raw` (optional), `severity`/`priority` (optional), `status_hint`, `related_item_title` (optional, for updates/reversals — matched to an earlier gold item's `title` by the generator, not a DB id, since gold is generated before any DB row exists)).

**Required content per chat** (author `sample_storyline.yaml` to satisfy all of these — this is the acceptance checklist, not optional flavor):

1. **`management_team`** (English-heavy, `android` format, DMY): at least 2 decisions, including one `reversed_decision` (a later message explicitly reverses/contradicts an earlier decision — worked example above). At least 1 unanswered-question scenario: a manager asks a direct question (`"Farah, what's the status on the Shapla contract renewal?"`) that gets no reply from anyone for the rest of the chat (`planted_scenario: unanswered_question`).
2. **`project_padma_warehouse`** (Banglish/English mix, `ios` format, DMY): at least 3 actions with explicit owners and relative-date deadlines using real Banglish/English relative-date phrases this plan's Task 3 date resolver must handle (`"kal"`, `"porshu"`, `"by Friday"`, `"EOD"` — spread across different action items, not all on one). At least one action whose deadline has clearly passed relative to the last message's date and is never marked done (`planted_scenario: overdue_action`), and at least one action that is planted overdue earlier but then explicitly marked complete in a later message, ideally with an informal completion phrase (`"done bhai ✅"`) (`planted_scenario: completed_late_action`).
3. **`ops_incidents`** (Bangla + English mix, `android` format, DMY): at least 1 risk item that is raised with clear severity language but **no owner is ever mentioned** for it (`planted_scenario: unowned_risk`, `severity: high`). At least one issue raised **3 separate times by different senders across at least 2 different `day` values**, each occurrence phrased a little differently but clearly the same underlying issue (`planted_scenario: recurring_issue` on the 3rd occurrence). Include real Bangla-script sentences for at least a few messages (not just Banglish) — e.g. `"গোডাউনে আবার লিকেজ হচ্ছে, গতকালও বলেছিলাম"`.
4. **`client_shapla_retail`** (English, `android` format, DMY): at least 1 client-escalation issue and a visible sentiment dip — 3–4 consecutive messages from the client contact using clearly negative/frustrated language in a short span (`planted_scenario: sentiment_dip`).
5. **`finance_approvals`** (English, `ios` format, DMY): at least 2 approval decisions, at least one of which is later reversed/contradicted (a second `reversed_decision`, independent of `management_team`'s).

Every chat additionally needs a handful of ordinary, non-planted messages (small talk, acknowledgements, status pings) so segments aren't 100% signal — this is what makes the Validator's grounding/precision checks meaningful in Task 5's real run. Aim for roughly 60–70% ordinary traffic, 30–40% items-bearing.

- [ ] **Step 1: write the failing generator test**

`backend/tests/scripts/test_generate_sample_data.py` (run from the backend venv since it imports `app.ingestion`; the script itself lives at repo-root `scripts/`, add repo root to `sys.path` in the test):
```python
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_sample_data import generate  # noqa: E402


def test_generates_all_five_chats_parseable(tmp_path):
    out_dir = tmp_path / "sample"
    generate(storyline_path=REPO_ROOT / "scripts" / "sample_storyline.yaml", out_dir=out_dir)

    exports_dir = out_dir / "exports"
    gold_dir = out_dir / "gold"
    export_files = sorted(exports_dir.iterdir())
    assert len(export_files) == 5

    from app.ingestion.export_parser.detect import detect_format
    from app.ingestion.export_parser.zip_loader import load_export_bytes

    for f in export_files:
        text, _media = load_export_bytes(f.read_bytes(), filename=f.name)
        fmt = detect_format(text)
        assert fmt in ("android", "ios")

    gold_files = sorted(gold_dir.iterdir())
    assert len(gold_files) == 5
    all_types = set()
    for f in gold_files:
        items = json.loads(f.read_text())
        assert isinstance(items, list) and len(items) > 0
        for item in items:
            assert item["type"] in ("action", "decision", "risk", "issue")
            assert "title" in item and "evidence_text" in item
            all_types.add(item["type"])
    assert all_types == {"action", "decision", "risk", "issue"}


def test_generation_is_deterministic(tmp_path):
    out1, out2 = tmp_path / "a", tmp_path / "b"
    generate(storyline_path=REPO_ROOT / "scripts" / "sample_storyline.yaml", out_dir=out1)
    generate(storyline_path=REPO_ROOT / "scripts" / "sample_storyline.yaml", out_dir=out2)
    for f1 in sorted((out1 / "gold").iterdir()):
        f2 = out2 / "gold" / f1.name
        assert f1.read_text() == f2.read_text()
```

- [ ] **Step 2: run, confirm failure (`ModuleNotFoundError: scripts`)**

- [ ] **Step 3: author `scripts/sample_storyline.yaml`** satisfying every bullet in "Required content per chat" above. Use the worked `management_team` example as the exact schema to follow; write all 5 chats' `messages` lists directly (there is no shortcut here — every message's `text` is real authored content).

- [ ] **Step 4: implement `scripts/generate_sample_data.py`**

```python
"""Deterministic sample-data generator (PLAN.md §11 / T1.2).

Reads `scripts/sample_storyline.yaml` and renders each chat to its
configured export format (Android .txt or iOS .zip containing `_chat.txt`),
plus a gold-labels JSON file per chat. No LLM call -- fully deterministic,
so re-running produces byte-identical output.
"""
import io
import json
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ANCHOR_DATE = date(2026, 1, 5)
TZ = ZoneInfo("Asia/Dhaka")


def _render_android_line(ts: datetime, sender: str | None, text: str) -> str:
    time_str = ts.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
    date_str = ts.strftime("%d/%m/%Y")
    prefix = f"{date_str}, {time_str} - "
    return prefix + (f"{sender}: {text}" if sender else text)


def _render_ios_line(ts: datetime, sender: str | None, text: str) -> str:
    time_str = ts.strftime("%I:%M:%S %p").lstrip("0")
    date_str = ts.strftime("%d/%m/%Y")
    prefix = f"[{date_str}, {time_str}] "
    return prefix + (f"{sender}: {text}" if sender else text)


def _render_chat(chat: dict) -> tuple[str, list[dict]]:
    lines: list[str] = []
    gold_items: list[dict] = []
    render = _render_android_line if chat["export_format"] == "android" else _render_ios_line

    for msg in chat["messages"]:
        ts = datetime.combine(
            ANCHOR_DATE + timedelta(days=msg["day"]),
            datetime.strptime(msg["time"], "%H:%M").time(),
            tzinfo=TZ,
        )
        sender = None if msg.get("system") else msg["sender"]
        lines.append(render(ts, sender, msg["text"]))
        if "gold" in msg:
            gold = dict(msg["gold"])
            gold["evidence_text"] = msg["text"]
            gold["chat_key"] = chat["key"]
            gold_items.append(gold)

    return "\n".join(lines), gold_items


def generate(*, storyline_path: Path, out_dir: Path) -> None:
    storyline = yaml.safe_load(storyline_path.read_text(encoding="utf-8"))
    exports_dir = out_dir / "exports"
    gold_dir = out_dir / "gold"
    exports_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    for chat in storyline["chats"]:
        text, gold_items = _render_chat(chat)
        if chat["export_format"] == "android":
            (exports_dir / f"{chat['key']}.txt").write_text(text, encoding="utf-8")
        else:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("_chat.txt", text.encode("utf-8"))
            (exports_dir / f"{chat['key']}.zip").write_bytes(buf.getvalue())

        (gold_dir / f"{chat['key']}.json").write_text(
            json.dumps(gold_items, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    generate(storyline_path=repo_root / "scripts" / "sample_storyline.yaml", out_dir=repo_root / "data" / "sample")
```

Add `"pyyaml>=6.0"` to `backend/pyproject.toml` `[project.dependencies]` (the generator imports it; running it via `uv run python scripts/generate_sample_data.py` from `backend/` resolves imports against the backend venv, so the dependency belongs there even though the script file lives at repo root).

- [ ] **Step 5: run the generator test, confirm pass**

Run: `cd backend && uv lock && uv sync && uv run pytest tests/scripts/test_generate_sample_data.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: generate and commit the real output**

```bash
cd backend && uv run python ../scripts/generate_sample_data.py
```
This writes `data/sample/exports/*` and `data/sample/gold/*` at the repo root. Inspect a couple of the generated files by hand to confirm the planted scenarios read naturally.

- [ ] **Step 7: whole-task verification, commit**

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest -q
```
```bash
git add scripts/sample_storyline.yaml scripts/generate_sample_data.py data/sample \
  backend/tests/scripts backend/pyproject.toml backend/uv.lock
git commit -m "feat: add deterministic sample-data generator with planted scenarios"
```

---

### Task 3: Segmentation + Date Resolver + Participant Resolver

**Files:**
- Create: `backend/app/services/segmentation.py`, `backend/app/services/date_resolver.py`
- Modify: `backend/app/services/participants.py` (add `resolve_participant`)
- Test: `backend/tests/services/test_segmentation.py`, `test_date_resolver.py`, extend `test_participants.py`

**Interfaces:**
- Consumes: `app.db.models.{Message, Segment, Participant}`, `app.db.session`.
- Produces: `build_segments(messages: list[Message], *, gap_minutes: int = 45, max_messages: int = 60) -> list[SegmentDraft]` where `SegmentDraft` has `.start_ts`, `.end_ts`, `.message_ids: list[uuid.UUID]`; `persist_pending_segments(session, chat_id) -> list[Segment]` (queries un-segmented messages, builds drafts, inserts `Segment` rows, returns them) — Task 5's `load_batch`/`segment` graph nodes call this directly. `resolve_date(raw: str, *, anchor_ts: datetime, tz: str = "Asia/Dhaka") -> datetime | None` — Task 5's Analyst step calls this as a deterministic tool per PLAN.md §6.2. `resolve_participant(name_or_mention: str, chat_id: uuid.UUID, session: Session) -> Participant | None` — Task 5's Analyst step calls this to resolve `owner_raw` text to a real participant.

- [ ] **Step 1: segmentation — write the failing tests**

`backend/tests/services/test_segmentation.py`:
```python
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
```

- [ ] **Step 2: run, confirm failure; implement; run, confirm pass**

```python
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Segment


class _HasTsAndId(Protocol):
    id: uuid.UUID
    ts: datetime


@dataclass
class SegmentDraft:
    start_ts: datetime
    end_ts: datetime
    message_ids: list[uuid.UUID] = field(default_factory=list)


def build_segments(
    messages: list[_HasTsAndId], *, gap_minutes: int = 45, max_messages: int = 60
) -> list[SegmentDraft]:
    if not messages:
        return []
    ordered = sorted(messages, key=lambda m: m.ts)
    gap = timedelta(minutes=gap_minutes)

    drafts: list[SegmentDraft] = []
    current = SegmentDraft(start_ts=ordered[0].ts, end_ts=ordered[0].ts, message_ids=[ordered[0].id])

    for prev, msg in zip(ordered, ordered[1:]):
        exceeds_gap = (msg.ts - prev.ts) > gap
        exceeds_count = len(current.message_ids) >= max_messages
        if exceeds_gap or exceeds_count:
            drafts.append(current)
            current = SegmentDraft(start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id])
        else:
            current.end_ts = msg.ts
            current.message_ids.append(msg.id)
    drafts.append(current)
    return drafts


def persist_pending_segments(session: Session, chat_id: uuid.UUID) -> list[Segment]:
    """Segments every message in `chat_id` that isn't already covered by an
    existing segment, in `ts` order. Simple v1 policy: a chat's *unsegmented
    tail* (messages newer than the chat's latest existing segment's
    `end_ts`, or every message if the chat has none yet) is (re)segmented
    each call -- safe to call repeatedly per incoming batch."""
    latest_end = session.scalar(
        select(Segment.end_ts).where(Segment.chat_id == chat_id).order_by(Segment.end_ts.desc()).limit(1)
    )
    query = select(Message).where(Message.chat_id == chat_id, Message.is_system.is_(False))
    if latest_end is not None:
        query = query.where(Message.ts > latest_end)
    pending = list(session.scalars(query.order_by(Message.ts)))

    drafts = build_segments(pending, gap_minutes=45, max_messages=60)
    segments = [
        Segment(
            chat_id=chat_id,
            start_ts=d.start_ts,
            end_ts=d.end_ts,
            message_ids=d.message_ids,
            analysis_status="pending",
        )
        for d in drafts
    ]
    session.add_all(segments)
    session.flush()
    return segments
```

Run: `cd backend && uv run pytest tests/services/test_segmentation.py -v` — Expected: PASS (6 tests).

- [ ] **Step 3: date resolver — write the failing tests**

`backend/tests/services/test_date_resolver.py`:
```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.date_resolver import resolve_date

TZ = "Asia/Dhaka"
ANCHOR = datetime(2026, 1, 5, 10, 0, tzinfo=ZoneInfo(TZ))  # a Monday


def test_today_english():
    assert resolve_date("today", anchor_ts=ANCHOR, tz=TZ).date() == ANCHOR.date()


def test_kal_is_tomorrow():
    result = resolve_date("kal", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == (ANCHOR.date().replace(day=6))


def test_porshu_is_day_after_tomorrow():
    result = resolve_date("porshu", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date().replace(day=7)


def test_next_friday():
    result = resolve_date("next Friday", anchor_ts=ANCHOR, tz=TZ)
    assert result.weekday() == 4  # Friday
    assert result.date() > ANCHOR.date()


def test_eod_means_end_of_anchor_day():
    result = resolve_date("EOD", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date()
    assert (result.hour, result.minute) == (23, 59)


def test_by_15th_resolves_within_current_month():
    result = resolve_date("by 15th", anchor_ts=ANCHOR, tz=TZ)
    assert (result.year, result.month, result.day) == (2026, 1, 15)


def test_by_ordinal_already_passed_rolls_to_next_month():
    result = resolve_date("by 2nd", anchor_ts=ANCHOR, tz=TZ)  # anchor is the 5th
    assert (result.year, result.month, result.day) == (2026, 2, 2)


def test_unresolvable_returns_none():
    assert resolve_date("sometime probably maybe", anchor_ts=ANCHOR, tz=TZ) is None


def test_explicit_dmy_date():
    result = resolve_date("15/03/2026", anchor_ts=ANCHOR, tz=TZ)
    assert (result.year, result.month, result.day) == (2026, 3, 15)


def test_never_resolves_before_anchor_date_for_relative_terms():
    # anchor is Monday; asking for "this Monday" should mean today, not last week
    result = resolve_date("this Monday", anchor_ts=ANCHOR, tz=TZ)
    assert result.date() == ANCHOR.date()
```

- [ ] **Step 4: run, confirm failure; implement `date_resolver.py`; run, confirm pass**

```python
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "sombar": 0, "mongolbar": 1, "budhbar": 2, "brihoshpotibar": 3, "shukrobar": 4,
    "shonibar": 5, "robibar": 6,
}
_RELATIVE_DAYS = {
    "today": 0, "aj": 0, "ajke": 0, "ajk": 0,
    "tomorrow": 1, "kal": 1, "agamikal": 1,
    "day after tomorrow": 2, "porshu": 2, "parsu": 2,
}
_EOD_RE = re.compile(r"^(eod|end of day)$")
_BY_ORDINAL_RE = re.compile(r"^by(\sthe)?\s(?P<day>\d{1,2})(st|nd|rd|th)?$")
_EXPLICIT_DATE_RE = re.compile(r"^(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4})$")
_WEEKDAY_PHRASE_RE = re.compile(r"^(this|next)?\s?(?P<weekday>[a-z]+)$")


def _pivot_year(year: int) -> int:
    return 2000 + year if year < 100 else year


def resolve_date(raw: str, *, anchor_ts: datetime, tz: str = "Asia/Dhaka") -> datetime | None:
    """Deterministic relative/explicit date resolution (PLAN.md §6.2's
    `resolve_date` tool). Returns `None` -- never a guessed date -- when the
    text doesn't match a known pattern; the caller (Analyst/Validator) must
    treat `None` as "keep due_date_raw, leave due_at unset", never invent a
    date (PLAN.md §6.3 deadline-sanity rule)."""
    zone = ZoneInfo(tz)
    anchor = anchor_ts.astimezone(zone)
    text = raw.strip().lower()

    if text in _RELATIVE_DAYS:
        target = anchor.date() + timedelta(days=_RELATIVE_DAYS[text])
        return datetime(target.year, target.month, target.day, 23, 59, tzinfo=zone)

    if _EOD_RE.match(text):
        return datetime(anchor.year, anchor.month, anchor.day, 23, 59, tzinfo=zone)

    m = _BY_ORDINAL_RE.match(text)
    if m:
        day = int(m.group("day"))
        year, month = anchor.year, anchor.month
        if day < anchor.day:
            month += 1
            if month > 12:
                month, year = 1, year + 1
        try:
            return datetime(year, month, day, 23, 59, tzinfo=zone)
        except ValueError:
            return None

    m = _EXPLICIT_DATE_RE.match(text)
    if m:
        day, month, year = int(m.group("d")), int(m.group("m")), _pivot_year(int(m.group("y")))
        try:
            return datetime(year, month, day, 23, 59, tzinfo=zone)
        except ValueError:
            return None

    m = _WEEKDAY_PHRASE_RE.match(text)
    if m and m.group("weekday") in _WEEKDAYS:
        target_weekday = _WEEKDAYS[m.group("weekday")]
        qualifier = m.group(1)
        days_ahead = (target_weekday - anchor.weekday()) % 7
        if qualifier == "next" and days_ahead == 0:
            days_ahead = 7
        elif qualifier == "next":
            days_ahead += 7
        target = anchor.date() + timedelta(days=days_ahead)
        return datetime(target.year, target.month, target.day, 23, 59, tzinfo=zone)

    return None
```

Run: `cd backend && uv run pytest tests/services/test_date_resolver.py -v` — Expected: PASS (10 tests).

- [ ] **Step 5: participant resolver — write the failing test**

Append to `backend/tests/services/test_participants.py`:
```python
from app.services.participants import resolve_participant


def test_resolves_exact_name(db_session, seed_chat):
    from app.services.participants import get_or_create_participant
    get_or_create_participant(db_session, seed_chat.id, "Rafi bhai")
    db_session.flush()
    result = resolve_participant("Rafi bhai", seed_chat.id, db_session)
    assert result is not None and result.display_name == "Rafi bhai"


def test_resolves_fuzzy_close_match(db_session, seed_chat):
    from app.services.participants import get_or_create_participant
    get_or_create_participant(db_session, seed_chat.id, "Rafiqul Islam")
    db_session.flush()
    result = resolve_participant("Rafiqul", seed_chat.id, db_session)
    assert result is not None and result.display_name == "Rafiqul Islam"


def test_strips_leading_at_mention():
    from app.services.participants import get_or_create_participant
    pass  # placeholder removed below -- see full test next


def test_at_mention_stripped(db_session, seed_chat):
    from app.services.participants import get_or_create_participant
    get_or_create_participant(db_session, seed_chat.id, "Nadia")
    db_session.flush()
    result = resolve_participant("@Nadia", seed_chat.id, db_session)
    assert result is not None and result.display_name == "Nadia"


def test_no_match_returns_none(db_session, seed_chat):
    result = resolve_participant("Someone Totally Unknown", seed_chat.id, db_session)
    assert result is None


def test_ambiguous_match_returns_none(db_session, seed_chat):
    from app.services.participants import get_or_create_participant
    get_or_create_participant(db_session, seed_chat.id, "Rahim")
    get_or_create_participant(db_session, seed_chat.id, "Rahim Uddin")
    db_session.flush()
    result = resolve_participant("Rahi", seed_chat.id, db_session)
    assert result is None
```
Delete the stray `test_strips_leading_at_mention` placeholder above before committing — it was left in this brief by mistake; write only the 5 real tests (`test_resolves_exact_name`, `test_resolves_fuzzy_close_match`, `test_at_mention_stripped`, `test_no_match_returns_none`, `test_ambiguous_match_returns_none`).

- [ ] **Step 6: run, confirm failure; implement `resolve_participant`; run, confirm pass**

Append to `backend/app/services/participants.py`:
```python
import difflib


def resolve_participant(name_or_mention: str, chat_id: uuid.UUID, session: Session) -> Participant | None:
    """Fuzzy-resolves an `owner_raw`/@mention string to a real participant
    in the chat. Returns `None` on no match or on an ambiguous match (the
    Validator's owner-check, PLAN.md §6.3, treats `None` as "owner
    unresolved", never guesses)."""
    name = name_or_mention.strip().lstrip("@").strip()
    if not name:
        return None

    exact = session.scalar(
        select(Participant).where(
            Participant.chat_id == chat_id,
            func.lower(Participant.display_name) == name.lower(),
        )
    )
    if exact is not None:
        return exact

    candidates = list(session.scalars(select(Participant).where(Participant.chat_id == chat_id)))
    names = [c.display_name for c in candidates]
    matches = difflib.get_close_matches(name, names, n=2, cutoff=0.6)
    if len(matches) != 1:
        return None
    return next(c for c in candidates if c.display_name == matches[0])
```

Run: `cd backend && uv run pytest tests/services/test_participants.py -v` — Expected: PASS (8 tests total: 3 from Task 1 + 5 here).

- [ ] **Step 7: whole-task verification, commit**

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest -q
```
```bash
git add backend/app/services/segmentation.py backend/app/services/date_resolver.py \
  backend/app/services/participants.py backend/tests/services/test_segmentation.py \
  backend/tests/services/test_date_resolver.py backend/tests/services/test_participants.py
git commit -m "feat: add segmentation, date resolver, and participant resolver"
```

---

### Task 4: Memory Module (embeddings write, hybrid retrieval, short-term chat state)

**Files:**
- Create: `backend/app/memory/__init__.py`, `backend/app/memory/short_term.py`, `backend/app/memory/long_term.py`, `backend/app/memory/retrieval.py`
- Create: `backend/alembic/versions/0003_chat_state.py`, `backend/alembic/versions/0004_fts_simple_config.py`
- Modify: `backend/app/db/models.py` (add `ChatState`)
- Test: `backend/tests/memory/test_short_term.py`, `test_long_term.py`, `test_retrieval.py`

**Interfaces:**
- Consumes: `app.db.models.{Message, Segment, Item}`, `app.llm.embeddings.EmbeddingProvider`, `app.llm.factory.get_embedding_provider`.
- Produces: `get_or_create_chat_state(session, chat_id) -> ChatState`, `update_rolling_summary(session, chat_id, summary: str) -> ChatState` (`memory/short_term.py`) — Task 5's Analyst step reads/writes this every batch. `embed_and_store_message(session, message, provider) -> None`, `embed_and_store_segment(...)`, `embed_and_store_item(...)` (`memory/long_term.py`) — Task 5's `memory_write` node calls these. `hybrid_search(session, query: str, provider: EmbeddingProvider, *, k: int = 10, chat_id: uuid.UUID | None = None) -> list[SearchResult]` (`memory/retrieval.py`) — Phase 2's Assistant tools (not this phase) will call this directly; this task's tests are the only consumer for now, so exercise it thoroughly.

- [ ] **Step 1: `ChatState` model + migration**

In `backend/app/db/models.py`, add (after `Chat`):
```python
class ChatState(Base):
    __tablename__ = "chat_state"

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    rolling_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_ts: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Generate the migration (`cd backend && uv run alembic revision --autogenerate -m "chat state table"`), rename the produced file to `0003_chat_state.py`, and inspect it — it must create exactly one table (`chat_state`) with the three columns above plus the PK; if autogenerate also picks up unrelated diffs (it shouldn't, since Phase 0's `0001`/`0002` already match current models otherwise), trim the migration to only the `chat_state` changes.

- [ ] **Step 2: FTS config fix migration**

`backend/alembic/versions/0004_fts_simple_config.py`:
```python
"""fix messages.tsv to use the `simple` text-search config

PLAN.md §7 requires `simple`, not `english`, specifically so Bangla and
Banglish tokens are not mangled by English stemming/stopwords. The Phase 0
migration (0002) used `english` by mistake; this corrects it without
touching that already-reviewed migration file.

Revision ID: <run `alembic revision` to get a real hash; do not hand-write one>
Revises: <the 0003 chat_state revision id>
"""
from alembic import op

revision = "<fill in>"
down_revision = "<fill in: 0003's revision id>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_tsv_gin")
    op.execute("ALTER TABLE messages DROP COLUMN tsv")
    op.execute(
        "ALTER TABLE messages "
        "ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED"
    )
    op.execute("CREATE INDEX ix_messages_tsv_gin ON messages USING gin (tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_tsv_gin")
    op.execute("ALTER TABLE messages DROP COLUMN tsv")
    op.execute(
        "ALTER TABLE messages "
        "ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )
    op.execute("CREATE INDEX ix_messages_tsv_gin ON messages USING gin (tsv)")
```
Generate this one as an empty revision (`uv run alembic revision -m "fix messages.tsv to use simple config"`) rather than autogenerate (autogenerate won't diff a `GENERATED ALWAYS AS` expression change), then fill in the `upgrade`/`downgrade` bodies exactly as above, and copy the real `revision`/`down_revision` ids alembic assigned into the header docstring's placeholders (replace the `<fill in>` text — do not leave it in the committed file).

Also update the corresponding `Message.tsv` comment in `backend/app/db/models.py` from "English config" to "simple config" — the SQLAlchemy column definition itself (`Computed("to_tsvector('english', text)", ...)`) must change to `Computed("to_tsvector('simple', text)", ...)` too, so a fresh `alembic upgrade head` and `Base.metadata.create_all` never disagree.

- [ ] **Step 3: apply migrations, confirm clean**

```bash
cd backend && uv run alembic upgrade head
```
Expected: both new revisions apply with no errors on top of Phase 0's `0001`/`0002`.

- [ ] **Step 4: short-term memory — write the failing tests**

`backend/tests/memory/test_short_term.py`:
```python
from app.memory.short_term import get_or_create_chat_state, update_rolling_summary


def test_creates_chat_state_on_first_access(db_session, seed_chat):
    state = get_or_create_chat_state(db_session, seed_chat.id)
    db_session.flush()
    assert state.chat_id == seed_chat.id
    assert state.rolling_summary is None


def test_returns_existing_state(db_session, seed_chat):
    s1 = get_or_create_chat_state(db_session, seed_chat.id)
    db_session.flush()
    s2 = get_or_create_chat_state(db_session, seed_chat.id)
    assert s1.chat_id == s2.chat_id


def test_update_rolling_summary_persists(db_session, seed_chat):
    get_or_create_chat_state(db_session, seed_chat.id)
    db_session.flush()
    updated = update_rolling_summary(db_session, seed_chat.id, "Team discussed Padma rollout timeline.")
    db_session.flush()
    assert updated.rolling_summary == "Team discussed Padma rollout timeline."
```

- [ ] **Step 5: implement `memory/short_term.py`, verify**

```python
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ChatState


def get_or_create_chat_state(session: Session, chat_id: uuid.UUID) -> ChatState:
    state = session.get(ChatState, chat_id)
    if state is not None:
        return state
    state = ChatState(chat_id=chat_id)
    session.add(state)
    session.flush()
    return state


def update_rolling_summary(
    session: Session, chat_id: uuid.UUID, summary: str, *, last_message_ts: datetime | None = None
) -> ChatState:
    state = get_or_create_chat_state(session, chat_id)
    state.rolling_summary = summary
    if last_message_ts is not None:
        state.last_message_ts = last_message_ts
    session.flush()
    return state
```

Run: `cd backend && uv run pytest tests/memory/test_short_term.py -v` — Expected: PASS (3 tests).

- [ ] **Step 6: long-term memory (embedding write) — write the failing tests**

`backend/tests/memory/test_long_term.py`:
```python
from app.llm.embeddings import FakeEmbeddingProvider
from app.memory.long_term import embed_and_store_item, embed_and_store_message, embed_and_store_segment


async def test_embeds_and_stores_message(db_session, seed_chat):
    from app.db.models import Message
    msg = Message(chat_id=seed_chat.id, ts=__import__("datetime").datetime.now(
        tz=__import__("zoneinfo").ZoneInfo("Asia/Dhaka")
    ), text="kal delivery hobe", content_hash="h1")
    db_session.add(msg)
    db_session.flush()

    await embed_and_store_message(db_session, msg, FakeEmbeddingProvider())
    db_session.flush()
    assert msg.embedding is not None
    assert len(msg.embedding) == 1024


async def test_embeds_and_stores_segment(db_session, seed_chat):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.db.models import Segment
    seg = Segment(
        chat_id=seed_chat.id,
        start_ts=datetime.now(tz=ZoneInfo("Asia/Dhaka")),
        end_ts=datetime.now(tz=ZoneInfo("Asia/Dhaka")),
        summary="Discussion about warehouse delivery timeline.",
    )
    db_session.add(seg)
    db_session.flush()
    await embed_and_store_segment(db_session, seg, FakeEmbeddingProvider())
    db_session.flush()
    assert seg.embedding is not None


async def test_embeds_and_stores_item(db_session, seed_chat):
    from app.db.models import Item
    item = Item(type="action", title="Deliver warehouse stock", chat_id=seed_chat.id)
    db_session.add(item)
    db_session.flush()
    await embed_and_store_item(db_session, item, FakeEmbeddingProvider())
    db_session.flush()
    assert item.embedding is not None


async def test_skips_embedding_when_text_empty(db_session, seed_chat):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.db.models import Message
    msg = Message(
        chat_id=seed_chat.id, ts=datetime.now(tz=ZoneInfo("Asia/Dhaka")), text="", content_hash="h2"
    )
    db_session.add(msg)
    db_session.flush()
    await embed_and_store_message(db_session, msg, FakeEmbeddingProvider())
    assert msg.embedding is None
```

- [ ] **Step 7: implement `memory/long_term.py`, verify**

```python
from app.db.models import Item, Message, Segment
from app.llm.embeddings import EmbeddingProvider


async def embed_and_store_message(session, message: Message, provider: EmbeddingProvider) -> None:
    if not message.text.strip():
        return
    [vector] = await provider.embed([message.text])
    message.embedding = vector
    session.flush()


async def embed_and_store_segment(session, segment: Segment, provider: EmbeddingProvider) -> None:
    text = segment.summary or segment.topic
    if not text or not text.strip():
        return
    [vector] = await provider.embed([text])
    segment.embedding = vector
    session.flush()


async def embed_and_store_item(session, item: Item, provider: EmbeddingProvider) -> None:
    text = f"{item.title}. {item.description or ''}".strip()
    if not text:
        return
    [vector] = await provider.embed([text])
    item.embedding = vector
    session.flush()
```
(`session` is typed `Session` — add the `from sqlalchemy.orm import Session` import and the `session: Session` annotation on all three; omitted above only for brevity, mypy requires it per Global Constraints.)

Run: `cd backend && uv run pytest tests/memory/test_long_term.py -v` — Expected: PASS (4 tests).

- [ ] **Step 8: hybrid retrieval — write the failing tests**

`backend/tests/memory/test_retrieval.py`:
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.models import Message
from app.llm.embeddings import FakeEmbeddingProvider
from app.memory.long_term import embed_and_store_message
from app.memory.retrieval import hybrid_search

TZ = ZoneInfo("Asia/Dhaka")


async def _seed_messages(db_session, seed_chat, provider):
    now = datetime.now(tz=TZ)
    texts = [
        "kal warehouse delivery confirm hobe",
        "গোডাউনে আবার লিকেজ হচ্ছে",
        "client meeting rescheduled to next week",
        "warehouse stock count completed",
    ]
    messages = []
    for i, text in enumerate(texts):
        msg = Message(chat_id=seed_chat.id, ts=now - timedelta(hours=i), text=text, content_hash=f"h{i}")
        db_session.add(msg)
        db_session.flush()
        await embed_and_store_message(db_session, msg, provider)
        messages.append(msg)
    db_session.flush()
    return messages


async def test_keyword_query_finds_matching_message(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "warehouse", provider, k=5, chat_id=seed_chat.id)
    assert any("warehouse" in r.text for r in results)


async def test_bangla_query_finds_bangla_message(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "গোডাউন লিকেজ", provider, k=5, chat_id=seed_chat.id)
    assert any("লিকেজ" in r.text for r in results)


async def test_results_carry_source_message_id(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "warehouse", provider, k=5, chat_id=seed_chat.id)
    assert all(r.message_id is not None for r in results)


async def test_chat_filter_excludes_other_chats(db_session, seed_chat, seed_chat_2):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    other = Message(
        chat_id=seed_chat_2.id, ts=datetime.now(tz=TZ), text="warehouse unrelated chat", content_hash="other1"
    )
    db_session.add(other)
    db_session.flush()
    await embed_and_store_message(db_session, other, provider)
    db_session.flush()

    results = await hybrid_search(db_session, "warehouse", provider, k=10, chat_id=seed_chat.id)
    assert all(r.chat_id == seed_chat.id for r in results)


async def test_k_limits_result_count(db_session, seed_chat):
    provider = FakeEmbeddingProvider()
    await _seed_messages(db_session, seed_chat, provider)
    results = await hybrid_search(db_session, "warehouse delivery client stock", provider, k=2)
    assert len(results) <= 2
```

- [ ] **Step 9: implement `memory/retrieval.py`, verify**

```python
import uuid

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Message
from app.llm.embeddings import EmbeddingProvider

_RRF_K = 60


class SearchResult(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    text: str
    score: float


async def hybrid_search(
    session: Session,
    query: str,
    provider: EmbeddingProvider,
    *,
    k: int = 10,
    chat_id: uuid.UUID | None = None,
) -> list[SearchResult]:
    """Fuses pgvector cosine search with Postgres full-text search (`simple`
    config, PLAN.md §7) via Reciprocal Rank Fusion: score = sum over the two
    rankers of 1/(RRF_K + rank). Every result carries `message_id` so
    citations are guaranteed (PLAN.md §7 "Context assembly")."""
    fetch_n = max(k * 4, 20)

    [query_vector] = await provider.embed([query])
    vector_stmt = (
        select(Message.id)
        .where(Message.embedding.is_not(None))
        .order_by(Message.embedding.cosine_distance(query_vector))
        .limit(fetch_n)
    )
    if chat_id is not None:
        vector_stmt = vector_stmt.where(Message.chat_id == chat_id)
    vector_ranked = list(session.scalars(vector_stmt))

    fts_stmt = (
        select(Message.id)
        .where(text("tsv @@ plainto_tsquery('simple', :q)"))
        .order_by(text("ts_rank(tsv, plainto_tsquery('simple', :q)) DESC"))
        .limit(fetch_n)
        .params(q=query)
    )
    if chat_id is not None:
        fts_stmt = fts_stmt.where(Message.chat_id == chat_id)
    fts_ranked = list(session.scalars(fts_stmt))

    scores: dict[uuid.UUID, float] = {}
    for rank, msg_id in enumerate(vector_ranked):
        scores[msg_id] = scores.get(msg_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, msg_id in enumerate(fts_ranked):
        scores[msg_id] = scores.get(msg_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    if not scores:
        return []

    top_ids = sorted(scores, key=lambda mid: scores[mid], reverse=True)[:k]
    rows = {m.id: m for m in session.scalars(select(Message).where(Message.id.in_(top_ids)))}
    return [
        SearchResult(message_id=mid, chat_id=rows[mid].chat_id, text=rows[mid].text, score=scores[mid])
        for mid in top_ids
        if mid in rows
    ]
```

Run: `cd backend && uv run pytest tests/memory/test_retrieval.py -v` — Expected: PASS (5 tests). If `test_bangla_query_finds_bangla_message` fails because the query embedding (a fake random vector, unrelated to real semantics) never ranks the Bangla message highly enough by vector search alone, that is expected — full-text search is what must surface it; if it still fails, the FTS config (Step 2) is the first thing to check (`SELECT to_tsvector('simple', text), plainto_tsquery('simple', 'গোডাউন লিকেজ') FROM messages;` in `psql` against the test DB to confirm tokens match).

- [ ] **Step 10: whole-task verification, commit**

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest -q
uv run alembic upgrade head   # against a clean throwaway DB, to confirm 0003+0004 apply cleanly from scratch
```
```bash
git add backend/app/memory backend/app/db/models.py backend/alembic/versions/0003_chat_state.py \
  backend/alembic/versions/0004_fts_simple_config.py backend/tests/memory
git commit -m "feat: add memory module (short-term chat state, embeddings, hybrid RRF retrieval)"
```

---

### Task 5: Analyst + Validator Agents + Pipeline Supervisor Graph + ARQ Worker

**Files:**
- Create: `backend/app/agents/__init__.py`, `state.py`, `agent_runs.py`, `analyst.py`, `validator.py`, `pipeline_graph.py`
- Create: `backend/app/agents/prompts/analyst_system.md`, `validator_judge_system.md`
- Create: `backend/app/workers/settings.py`, `backend/app/workers/jobs.py`
- Modify: `backend/pyproject.toml` (add `langgraph`)
- Test: `backend/tests/agents/test_analyst.py`, `test_validator.py`, `test_pipeline_graph.py`, `backend/tests/workers/test_jobs.py`

**Interfaces:**
- Consumes: `app.llm.base.{LLMProvider, ChatMessage}`, `app.llm.factory.get_llm_provider`, `app.schemas.item.ExtractedItem`, `app.schemas.validation.ValidationReport`, `app.schemas.segment.SegmentOut`, Task 3's `build_segments`/`persist_pending_segments`/`resolve_date`/`resolve_participant`, Task 4's `get_or_create_chat_state`/`update_rolling_summary`/`embed_and_store_*`, `app.db.models.{AgentRun, Item, ItemEvidence, Segment}`.
- Produces: `build_pipeline_graph(llm: LLMProvider, embedder: EmbeddingProvider) -> CompiledGraph` — nothing later in this plan consumes it (Phase 2's Monitor/Action agents are separate graphs), but `workers/jobs.py`'s `process_batch` is its only caller, so keep the constructor signature exactly this shape.

- [ ] **Step 1: agent_runs logging helper — write the failing test**

`backend/tests/agents/test_agent_runs.py`... actually keep this inside `test_pipeline_graph.py` (it's exercised end-to-end there); write one direct unit test:

`backend/tests/agents/test_agent_runs_helper.py`:
```python
from app.agents.agent_runs import log_agent_run
from app.db.models import AgentRun


def test_logs_a_run_row(db_session):
    log_agent_run(
        db_session, run_id="run-1", agent="pipeline", node="analyse", iteration=1,
        status="ok", input_summary="segment abc", output_summary="3 items", model="fake-model",
        tokens_in=10, tokens_out=20, latency_ms=5,
    )
    db_session.flush()
    row = db_session.query(AgentRun).filter(AgentRun.run_id == "run-1").one()
    assert row.node == "analyse" and row.status == "ok"
```

- [ ] **Step 2: implement `agents/agent_runs.py`, verify**

```python
from sqlalchemy.orm import Session

from app.db.models import AgentRun


def log_agent_run(
    session: Session,
    *,
    run_id: str,
    agent: str,
    node: str,
    iteration: int = 0,
    status: str,
    input_summary: str | None = None,
    output_summary: str | None = None,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
) -> AgentRun:
    run = AgentRun(
        run_id=run_id, agent=agent, node=node, iteration=iteration, status=status,
        input_summary=input_summary, output_summary=output_summary, model=model,
        tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms, error=error,
    )
    session.add(run)
    session.flush()
    return run
```

Run: `cd backend && uv run pytest tests/agents/test_agent_runs_helper.py -v` — Expected: PASS.

- [ ] **Step 3: prompts**

`backend/app/agents/prompts/analyst_system.md`:
```markdown
You are the Analyst agent for a management-intelligence system that reads
WhatsApp group chat segments and extracts actions, decisions, risks and
issues for managers to track.

For the given segment (messages with id, sender, timestamp), produce:
1. A classification: topic (short phrase), category (one of: project_update,
   incident, planning, approval, client, hr, social, other), sentiment
   (positive, neutral, negative), urgency (low, medium, high), and the
   language mix present (e.g. "English", "Bangla", "Banglish", "mixed").
2. A list of extracted items. Each item has: type (action, decision, risk,
   or issue), title (short), description, owner_raw (the name/mention as
   written, or null if unowned), due_date_raw (the date phrase as written,
   e.g. "kal", "by Friday", or null), priority, severity (for risks),
   likelihood (for risks), status_hint (new, update, completed, or
   cancelled -- "update"/"completed" when the segment clearly refers back
   to something raised earlier), evidence (a list of {message_id, quote}
   pairs -- quote must be copied verbatim from the cited message's text,
   not paraphrased), and confidence (0.0-1.0).

Messages are in English, Bangla script, and Banglish (romanized Bangla),
sometimes mixed in one message. Extract item titles/descriptions in
English; keep evidence quotes in the original language exactly as written.

Never invent a due date, owner, or fact not present in the messages. If
unsure, lower confidence or omit the field rather than guessing.

If given validator feedback from a previous attempt, treat it as
authoritative: fix exactly the problems named, and do not otherwise change
items that weren't flagged.
```

`backend/app/agents/prompts/validator_judge_system.md`:
```markdown
You are the Validator agent's LLM-judge step. You are given one extracted
item (type, title, description, evidence quotes) and the segment's source
messages. Answer only: is this genuinely a management-relevant action,
decision, risk, or issue, clearly supported by the cited evidence -- not a
throwaway remark, joke, or unrelated chatter? Return a confidence score
from 0.0 (definitely not, or evidence doesn't support it) to 1.0
(definitely yes, well supported).
```

- [ ] **Step 4: pipeline state**

`backend/app/agents/state.py`:
```python
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
```

- [ ] **Step 5: Analyst — write the failing tests**

`backend/tests/agents/test_analyst.py`:
```python
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agents.analyst import run_analyst
from app.db.models import Message, Segment
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem

TZ = ZoneInfo("Asia/Dhaka")


def _seed_segment(db_session, seed_chat):
    msg = Message(
        chat_id=seed_chat.id, ts=datetime.now(tz=TZ), text="kal warehouse stock pathabo",
        content_hash="analyst-h1",
    )
    db_session.add(msg)
    db_session.flush()
    seg = Segment(
        chat_id=seed_chat.id, start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id],
        analysis_status="pending",
    )
    db_session.add(seg)
    db_session.flush()
    return seg, msg


async def test_returns_extracted_items_from_scripted_llm(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    scripted = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi", due_date_raw="kal",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")],
        confidence=0.8,
    )
    provider = FakeProvider(structured_responses=[{"items": [scripted.model_dump(mode="json")], "topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium"}])

    result = await run_analyst(db_session, segment=seg, llm=provider, feedback=None)

    assert len(result.items) == 1
    assert result.items[0].title == "Send warehouse stock"


async def test_passes_feedback_into_prompt_when_retrying(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    scripted = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")], confidence=0.9,
    )
    provider = FakeProvider(structured_responses=[{"items": [scripted.model_dump(mode="json")], "topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium"}])

    await run_analyst(db_session, segment=seg, llm=provider, feedback="item 1: owner ambiguous")

    sent_messages = provider.calls[0]["messages"]
    assert any("owner ambiguous" in m["content"] for m in sent_messages)
```

Note: `run_analyst`'s structured-output response model needs a wrapper (`AnalystOutput`) since the Analyst returns both a classification and a list of items in one call — define it in `analyst.py` itself (it's an internal LLM-response shape, not a shared contract, so it does not belong in `app/schemas/`):
```python
class AnalystOutput(BaseModel):
    topic: str
    category: str
    sentiment: str
    urgency: str
    items: list[ExtractedItem]
```

- [ ] **Step 6: implement `agents/analyst.py`, verify**

```python
import time
import uuid
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Segment
from app.llm.base import ChatMessage, LLMProvider
from app.schemas.item import ExtractedItem

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "analyst_system.md").read_text()


class AnalystOutput(BaseModel):
    topic: str
    category: str
    sentiment: str
    urgency: str
    items: list[ExtractedItem]


class AnalystResult(AnalystOutput):
    pass


async def run_analyst(
    session: Session, *, segment: Segment, llm: LLMProvider, feedback: str | None
) -> AnalystResult:
    messages = list(
        session.scalars(select(Message).where(Message.id.in_(segment.message_ids)).order_by(Message.ts))
    )
    transcript = "\n".join(f"[{m.id}] {m.ts.isoformat()} - {m.text}" for m in messages)

    user_content = f"Segment messages:\n{transcript}"
    if feedback:
        user_content += f"\n\nValidator feedback from previous attempt (fix these exactly):\n{feedback}"

    chat_messages: list[ChatMessage] = [{"role": "user", "content": user_content}]
    output = await llm.structured(chat_messages, response_model=AnalystOutput, system=_SYSTEM_PROMPT)
    return AnalystResult(**output.model_dump())
```

Run: `cd backend && uv run pytest tests/agents/test_analyst.py -v` — Expected: PASS (2 tests).

- [ ] **Step 7: Validator — write the failing tests**

`backend/tests/agents/test_validator.py`:
```python
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agents.validator import run_validator
from app.db.models import Message, Segment
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem

TZ = ZoneInfo("Asia/Dhaka")


def _seed_segment(db_session, seed_chat, text="kal warehouse stock pathabo"):
    msg = Message(chat_id=seed_chat.id, ts=datetime.now(tz=TZ), text=text, content_hash=str(uuid.uuid4()))
    db_session.add(msg)
    db_session.flush()
    seg = Segment(chat_id=seed_chat.id, start_ts=msg.ts, end_ts=msg.ts, message_ids=[msg.id])
    db_session.add(seg)
    db_session.flush()
    return seg, msg


async def test_passes_when_evidence_grounds_and_judge_confident(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")], confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is True
    assert report.per_item_verdicts[0].passed is True


async def test_fails_when_quote_not_found_in_cited_message(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msg.id, quote="this text is not in the message")],
        confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is False
    assert any("quote" in i.message.lower() for i in report.per_item_verdicts[0].issues)


async def test_fails_when_evidence_message_id_outside_segment(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    foreign_id = uuid.uuid4()
    item = ExtractedItem(
        type="action", title="Send stock",
        evidence=[EvidenceRef(message_id=foreign_id, quote="kal warehouse stock pathabo")],
        confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is False


async def test_low_judge_confidence_fails_item(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock",
        evidence=[EvidenceRef(message_id=msg.id, quote="kal warehouse stock pathabo")], confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.2}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.passed is False


async def test_feedback_string_summarizes_issues(db_session, seed_chat):
    seg, msg = _seed_segment(db_session, seed_chat)
    item = ExtractedItem(
        type="action", title="Send stock",
        evidence=[EvidenceRef(message_id=msg.id, quote="not present in message")], confidence=0.8,
    )
    judge = FakeProvider(structured_responses=[{"confidence": 0.9}])
    report = await run_validator(db_session, segment=seg, items=[item], judge_llm=judge)
    assert report.feedback is not None and "item 1" in report.feedback.lower()
```

- [ ] **Step 8: implement `agents/validator.py`, verify**

```python
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Segment
from app.llm.base import ChatMessage, LLMProvider
from app.schemas.item import ExtractedItem
from app.schemas.validation import ItemVerdict, ValidationIssue, ValidationReport

_JUDGE_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "validator_judge_system.md").read_text()
_QUOTE_MATCH_THRESHOLD = 0.8
_JUDGE_CONFIDENCE_THRESHOLD = 0.5


class _JudgeOutput(BaseModel):
    confidence: float


def _quote_grounded(quote: str, message_text: str) -> bool:
    if quote in message_text:
        return True
    return SequenceMatcher(None, quote, message_text).ratio() >= _QUOTE_MATCH_THRESHOLD


async def run_validator(
    session: Session, *, segment: Segment, items: list[ExtractedItem], judge_llm: LLMProvider
) -> ValidationReport:
    from app.db.models import Message
    from sqlalchemy import select

    segment_messages = {
        m.id: m for m in session.scalars(select(Message).where(Message.id.in_(segment.message_ids)))
    }

    verdicts: list[ItemVerdict] = []
    all_issues: list[ValidationIssue] = []

    for idx, item in enumerate(items):
        issues: list[ValidationIssue] = []

        if not item.evidence:
            issues.append(ValidationIssue(item_index=idx, field="evidence", message="no evidence cited"))
        for ev in item.evidence:
            source = segment_messages.get(ev.message_id)
            if source is None:
                issues.append(
                    ValidationIssue(
                        item_index=idx, field="evidence",
                        message=f"cited message {ev.message_id} is not in this segment",
                    )
                )
                continue
            if not _quote_grounded(ev.quote, source.text):
                issues.append(
                    ValidationIssue(
                        item_index=idx, field="evidence",
                        message=f"quote not found in message {ev.message_id}",
                    )
                )

        judge_confidence = None
        if not issues:
            judge_result = await judge_llm.structured(
                [{"role": "user", "content": f"Item: {item.title}. Evidence: {[e.quote for e in item.evidence]}"}],
                response_model=_JudgeOutput,
                system=_JUDGE_SYSTEM_PROMPT,
            )
            judge_confidence = judge_result.confidence
            if judge_confidence < _JUDGE_CONFIDENCE_THRESHOLD:
                issues.append(
                    ValidationIssue(
                        item_index=idx, field=None,
                        message=f"judge confidence {judge_confidence:.2f} below threshold",
                    )
                )

        passed = not issues
        verdicts.append(ItemVerdict(item_index=idx, passed=passed, confidence=judge_confidence, issues=issues))
        all_issues.extend(issues)

    overall_passed = all(v.passed for v in verdicts) if verdicts else False
    feedback = None
    if not overall_passed:
        lines = [f"item {i + 1}: {issue.message}" for i, v in enumerate(verdicts) for issue in v.issues]
        feedback = "; ".join(lines)

    return ValidationReport(
        passed=overall_passed, issues=all_issues, per_item_verdicts=verdicts, feedback=feedback
    )
```

Run: `cd backend && uv run pytest tests/agents/test_validator.py -v` — Expected: PASS (5 tests).

- [ ] **Step 9: pipeline graph — write the failing tests**

`backend/tests/agents/test_pipeline_graph.py`:
```python
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.agents.pipeline_graph import run_pipeline_for_chat
from app.db.models import AgentRun, Item, Message
from app.llm.embeddings import FakeEmbeddingProvider
from app.llm.fake_provider import FakeProvider
from app.schemas.item import EvidenceRef, ExtractedItem

TZ = ZoneInfo("Asia/Dhaka")


def _seed_messages(db_session, seed_chat):
    now = datetime.now(tz=TZ)
    m1 = Message(chat_id=seed_chat.id, ts=now, text="kal warehouse stock pathabo", content_hash=str(uuid.uuid4()))
    m2 = Message(
        chat_id=seed_chat.id, ts=now + timedelta(minutes=2), text="thik ache Rafi", content_hash=str(uuid.uuid4())
    )
    db_session.add_all([m1, m2])
    db_session.flush()
    return [m1, m2]


async def test_pipeline_passes_on_first_try_and_stores_items(db_session, seed_chat):
    msgs = _seed_messages(db_session, seed_chat)
    good_item = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="kal warehouse stock pathabo")], confidence=0.9,
    )
    analyst_llm = FakeProvider(
        structured_responses=[
            {"topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium",
             "items": [good_item.model_dump(mode="json")]},
        ]
    )
    judge_llm = FakeProvider(structured_responses=[{"confidence": 0.9}])

    await run_pipeline_for_chat(
        db_session, chat_id=seed_chat.id, analyst_llm=analyst_llm, judge_llm=judge_llm,
        embedder=FakeEmbeddingProvider(),
    )
    db_session.commit()

    items = db_session.query(Item).filter(Item.chat_id == seed_chat.id).all()
    assert len(items) == 1
    assert items[0].validation_status == "passed"

    runs = db_session.query(AgentRun).filter(AgentRun.agent == "pipeline").all()
    nodes = {r.node for r in runs}
    assert {"load_batch", "segment", "analyse", "validate", "memory_write"} <= nodes


async def test_pipeline_retries_after_validator_feedback_then_passes(db_session, seed_chat):
    msgs = _seed_messages(db_session, seed_chat)
    bad_item = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="text that is not actually in the message")],
        confidence=0.9,
    )
    good_item = ExtractedItem(
        type="action", title="Send warehouse stock", owner_raw="Rafi",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="kal warehouse stock pathabo")], confidence=0.9,
    )
    analyst_llm = FakeProvider(
        structured_responses=[
            {"topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium",
             "items": [bad_item.model_dump(mode="json")]},
            {"topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium",
             "items": [good_item.model_dump(mode="json")]},
        ]
    )
    judge_llm = FakeProvider(structured_responses=[{"confidence": 0.9}])

    await run_pipeline_for_chat(
        db_session, chat_id=seed_chat.id, analyst_llm=analyst_llm, judge_llm=judge_llm,
        embedder=FakeEmbeddingProvider(),
    )
    db_session.commit()

    items = db_session.query(Item).filter(Item.chat_id == seed_chat.id).all()
    assert len(items) == 1
    assert items[0].validation_status == "passed"

    runs = db_session.query(AgentRun).filter(AgentRun.agent == "pipeline", AgentRun.node == "analyse").all()
    assert len(runs) == 2  # proves the retry happened


async def test_pipeline_routes_to_needs_review_after_three_failures(db_session, seed_chat):
    msgs = _seed_messages(db_session, seed_chat)
    bad_item = ExtractedItem(
        type="action", title="Send warehouse stock",
        evidence=[EvidenceRef(message_id=msgs[0].id, quote="never appears anywhere")], confidence=0.9,
    )
    analyst_llm = FakeProvider(
        structured_responses=[
            {"topic": "logistics", "category": "project_update", "sentiment": "neutral", "urgency": "medium",
             "items": [bad_item.model_dump(mode="json")]},
        ]
    )  # single scripted response, cursor wraps -- same bad item every retry
    judge_llm = FakeProvider(structured_responses=[{"confidence": 0.9}])

    await run_pipeline_for_chat(
        db_session, chat_id=seed_chat.id, analyst_llm=analyst_llm, judge_llm=judge_llm,
        embedder=FakeEmbeddingProvider(),
    )
    db_session.commit()

    items = db_session.query(Item).filter(Item.chat_id == seed_chat.id).all()
    assert len(items) == 1
    assert items[0].validation_status == "needs_review"

    runs = db_session.query(AgentRun).filter(AgentRun.agent == "pipeline", AgentRun.node == "analyse").all()
    assert len(runs) == 3  # exactly 3 attempts, never more
```

- [ ] **Step 10: implement `agents/pipeline_graph.py`, verify**

Use LangGraph's `StateGraph`. Check the installed version's exact import paths first (`cd backend && uv run python -c "import langgraph; print(langgraph.__version__)"` after Step 12 installs it) — the shape below (`StateGraph`, `END`, `add_node`, `add_edge`, `add_conditional_edges`, `set_entry_point`, `.compile()`) has been stable across LangGraph 0.x; adapt import paths only if the installed version genuinely requires it, keeping the same five-node graph shape and the same routing rule (retry ≤3, then `needs_review`).

```python
import time
import uuid

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.agent_runs import log_agent_run
from app.agents.analyst import run_analyst
from app.agents.state import PipelineState
from app.agents.validator import run_validator
from app.db.models import Item, ItemEvidence, Segment
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingProvider
from app.memory.long_term import embed_and_store_item, embed_and_store_message, embed_and_store_segment
from app.memory.short_term import update_rolling_summary
from app.services.date_resolver import resolve_date
from app.services.participants import resolve_participant
from app.services.segmentation import persist_pending_segments

_MAX_ITERATIONS = 3


def _build_graph(session: Session, llm: LLMProvider, judge_llm: LLMProvider, embedder: EmbeddingProvider):
    async def analyse_node(state: PipelineState) -> PipelineState:
        segment = session.get(Segment, state["segment_id"])
        start = time.perf_counter()
        result = await run_analyst(session, segment=segment, llm=llm, feedback=state["feedback"])
        log_agent_run(
            session, run_id=state["run_id"], agent="pipeline", node="analyse",
            iteration=state["iteration"], status="ok",
            input_summary=f"segment {segment.id}", output_summary=f"{len(result.items)} items",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
        segment.topic, segment.category = result.topic, result.category
        segment.sentiment, segment.urgency = result.sentiment, result.urgency
        return {**state, "candidate_items": result.items, "iteration": state["iteration"] + 1}

    async def validate_node(state: PipelineState) -> PipelineState:
        segment = session.get(Segment, state["segment_id"])
        report = await run_validator(
            session, segment=segment, items=state["candidate_items"], judge_llm=judge_llm
        )
        log_agent_run(
            session, run_id=state["run_id"], agent="pipeline", node="validate",
            iteration=state["iteration"], status="ok" if report.passed else "failed",
            output_summary=report.feedback or "passed",
        )
        return {**state, "validation": report, "feedback": report.feedback}

    def route_after_validate(state: PipelineState) -> str:
        report = state["validation"]
        if report.passed:
            return "pass"
        if state["iteration"] >= _MAX_ITERATIONS:
            return "needs_review"
        return "retry"

    async def memory_write_node(state: PipelineState) -> PipelineState:
        segment = session.get(Segment, state["segment_id"])
        status = "passed" if state["status"] != "needs_review" else "needs_review"
        for extracted in state["candidate_items"]:
            owner_participant = None
            if extracted.owner_raw:
                owner_participant = resolve_participant(extracted.owner_raw, segment.chat_id, session)
            due_at = extracted.due_at
            if due_at is None and extracted.due_date_raw:
                due_at = resolve_date(extracted.due_date_raw, anchor_ts=segment.end_ts)

            item = Item(
                type=extracted.type, title=extracted.title, description=extracted.description,
                chat_id=segment.chat_id, segment_id=segment.id,
                owner_participant_id=owner_participant.id if owner_participant else None,
                owner_raw=extracted.owner_raw, due_at=due_at, due_raw=extracted.due_date_raw,
                priority=extracted.priority, severity=extracted.severity, likelihood=extracted.likelihood,
                confidence=extracted.confidence, validation_status=status,
            )
            session.add(item)
            session.flush()
            for ev in extracted.evidence:
                session.add(ItemEvidence(item_id=item.id, message_id=ev.message_id, quote=ev.quote))
            await embed_and_store_item(session, item, embedder)

        segment.analysis_status = "done" if status == "passed" else "needs_review"
        await embed_and_store_segment(session, segment, embedder)
        update_rolling_summary(
            session, segment.chat_id, segment.summary or segment.topic or "", last_message_ts=segment.end_ts
        )
        session.flush()
        log_agent_run(session, run_id=state["run_id"], agent="pipeline", node="memory_write", status="ok")
        return state

    graph = StateGraph(PipelineState)
    graph.add_node("analyse", analyse_node)
    graph.add_node("validate", validate_node)
    graph.add_node("memory_write", memory_write_node)
    graph.set_entry_point("analyse")
    graph.add_edge("analyse", "validate")
    graph.add_conditional_edges(
        "validate", route_after_validate,
        {"retry": "analyse", "needs_review": "memory_write", "pass": "memory_write"},
    )
    graph.add_edge("memory_write", END)
    return graph.compile()


async def run_pipeline_for_chat(
    session: Session,
    *,
    chat_id: uuid.UUID,
    analyst_llm: LLMProvider,
    judge_llm: LLMProvider,
    embedder: EmbeddingProvider,
) -> None:
    """`load_batch` + `segment` happen here, outside the compiled graph,
    because they operate once per *chat batch* (many segments), while the
    compiled graph below runs once per *segment* (the analyse<->validate
    retry loop is segment-scoped, per PLAN.md §4.1)."""
    run_id = str(uuid.uuid4())
    start = time.perf_counter()
    unembedded = [m for m in session.query(__import__("app.db.models", fromlist=["Message"]).Message)
                  .filter_by(chat_id=chat_id).all() if m.embedding is None]
    for message in unembedded:
        await embed_and_store_message(session, message, embedder)
    log_agent_run(
        session, run_id=run_id, agent="pipeline", node="load_batch", status="ok",
        output_summary=f"{len(unembedded)} messages embedded",
        latency_ms=int((time.perf_counter() - start) * 1000),
    )

    start = time.perf_counter()
    segments = persist_pending_segments(session, chat_id)
    log_agent_run(
        session, run_id=run_id, agent="pipeline", node="segment", status="ok",
        output_summary=f"{len(segments)} segments", latency_ms=int((time.perf_counter() - start) * 1000),
    )

    graph = _build_graph(session, analyst_llm, judge_llm, embedder)
    for segment in segments:
        initial_state: PipelineState = {
            "run_id": run_id, "chat_id": chat_id, "segment_id": segment.id, "iteration": 0,
            "candidate_items": [], "validation": None, "feedback": None, "status": "in_progress",
        }
        await graph.ainvoke(initial_state)
```
Clean up the `unembedded` line's inline import once written — use a normal top-of-file `from app.db.models import Message` import instead (it was written inline above only to fit the brief's formatting; a normal import is required by the Global Constraints' lint rules and is the only acceptable form in the actual commit).

Run: `cd backend && uv run pytest tests/agents/test_pipeline_graph.py -v` — Expected: PASS (3 tests). If LangGraph's actual installed API rejects any call shape above (async node functions, `set_entry_point`, dict-based conditional edge routing), adapt to match the installed version's real signatures — these are the most likely spots for minor drift between LangGraph releases — while preserving the graph's node set and routing behavior exactly as specified in this plan and verified by these three tests.

- [ ] **Step 11: ARQ worker — write the failing test**

`backend/tests/workers/test_jobs.py`:
```python
from unittest.mock import AsyncMock, patch

from app.workers.jobs import process_batch


async def test_process_batch_invokes_pipeline(seed_chat):
    with patch("app.workers.jobs.run_pipeline_for_chat", new=AsyncMock()) as mock_run:
        await process_batch({}, str(seed_chat.id))
        mock_run.assert_awaited_once()
        assert mock_run.call_args.kwargs["chat_id"] == seed_chat.id
```
(This test needs the `seed_chat` fixture without `db_session` being a required first arg for `process_batch` itself, since the real job opens its own session — check `backend/tests/services/conftest.py`'s fixtures are visible here too, or add a thin `backend/tests/workers/conftest.py` that imports the same `db_session`/`seed_chat` fixtures.)

- [ ] **Step 12: implement `app/workers/settings.py`, `app/workers/jobs.py`; add `langgraph` dependency; verify**

`backend/app/workers/jobs.py`:
```python
from app.agents.pipeline_graph import run_pipeline_for_chat
from app.db.session import SessionLocal
from app.llm.factory import get_embedding_provider, get_llm_provider


async def process_batch(ctx: dict, chat_id: str) -> dict:
    session = SessionLocal()
    try:
        llm = get_llm_provider()
        embedder = get_embedding_provider()
        await run_pipeline_for_chat(
            session, chat_id=__import__("uuid").UUID(chat_id),
            analyst_llm=llm, judge_llm=llm, embedder=embedder,
        )
        session.commit()
        return {"chat_id": chat_id, "status": "ok"}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```
Replace the inline `__import__("uuid")` with a proper `import uuid` at the top of the file in the real commit — same note as Step 10.

`backend/app/workers/settings.py`:
```python
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.jobs import process_batch


class WorkerSettings:
    functions = [process_batch]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
```

Add `"langgraph>=0.2,<0.3"` to `backend/pyproject.toml` `[project.dependencies]`, then:
```bash
cd backend
uv lock
uv sync
uv run pytest tests/workers/test_jobs.py -v
```
Expected: PASS (1 test).

- [ ] **Step 13: real end-to-end sanity run on sample data (manual, not an automated test)**

With `LLM_PROVIDER=fake` still set (no real API key needed), confirm the whole chain works against Task 2's generated sample data:
```bash
cd .. && docker compose up -d postgres redis && cd backend
uv run alembic upgrade head
uv run python -c "
import asyncio
from app.db.session import SessionLocal
from app.db.models import Chat
from app.services.ingestion import ingest_export
from app.agents.pipeline_graph import run_pipeline_for_chat
from app.llm.fake_provider import FakeProvider
from app.llm.embeddings import FakeEmbeddingProvider

async def main():
    session = SessionLocal()
    chat = Chat(source='export', name='Sanity Check', type='group', timezone='Asia/Dhaka')
    session.add(chat); session.flush()
    data = open('../data/sample/exports/project_padma_warehouse.txt', 'rb').read()
    await ingest_export(session, chat_id=chat.id, filename='padma.txt', file_bytes=data, date_order='DMY', enqueue=None)
    session.commit()
    llm = FakeProvider(structured_responses=[{'topic':'logistics','category':'project_update','sentiment':'neutral','urgency':'medium','items':[]}])
    await run_pipeline_for_chat(session, chat_id=chat.id, analyst_llm=llm, judge_llm=llm, embedder=FakeEmbeddingProvider())
    session.commit()
    print('ok')

asyncio.run(main())
"
```
This won't produce meaningful extracted items (the `FakeProvider` above is scripted to return zero items — real extraction needs either a real provider or a script built from the sample data's actual text, which is more setup than a sanity check needs) — its only job is to prove the full ingest → segment → analyse → validate → memory_write chain runs end-to-end against real sample-data text with zero exceptions. If it prints `ok`, the chain works. This step is exploratory verification, not a commit gate — do not add it as a test file.

- [ ] **Step 14: whole-task verification, commit**

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest -q
```
```bash
git add backend/app/agents backend/app/workers backend/pyproject.toml backend/uv.lock \
  backend/tests/agents backend/tests/workers
git commit -m "feat: add Analyst/Validator agents, pipeline supervisor graph, and ARQ worker"
```

---

## Self-Review Notes (for whoever runs the final whole-branch review of this phase)

- Task 5's `run_pipeline_for_chat` re-queries every message in the chat with `embedding is None` on every batch (Step 10) rather than tracking exactly which messages are new — fine for the sample-data scale in this phase, but flag it as a future efficiency concern (index on `messages.embedding IS NULL` or a `needs_embedding` flag) once real chat volumes matter — do not silently "optimize" this during implementation, it's an intentional YAGNI call for now.
- `_content_hash` in Task 1's `services/ingestion.py` re-implements the exact hash formula PLAN.md §10 specifies (`sha256(chat_id, ts, sender, text)`) — if any task changes `Message` field semantics later, this formula must move with it; it is duplicated nowhere else.
- The Assistant/Monitor/Action agents (Phase 2) will need their own `agent_runs` `agent` values (`"monitor"`, `"action"`, `"assistant"`) — this plan's Global Constraints intentionally scope `agent="pipeline"` only to keep this phase's own acceptance criteria checkable; do not treat the Global Constraints list as exhaustive for the whole project.
