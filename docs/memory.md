# Memory Design

| Layer | What | Store | Lifetime / refresh |
|---|---|---|---|
| **Working memory** | One pipeline run's state (segment, candidate items, validator feedback, iteration count) | LangGraph `PipelineState` (in-process) | Single graph run |
| **Short-term: conversation** | Chat's rolling summary, updated after each batch | `chat_state` table (`memory/short_term.py`) | Rolling |
| **Short-term: assistant** | Per-thread dialogue history | LangGraph Postgres checkpointer, `thread_id = assistant:{user}:{thread}` (`agents/assistant_memory.py`) | Per thread |
| **Short-term: action approval** | Paused approval-gate run state | LangGraph Postgres checkpointer (`agents/checkpoints.py`) | Until approved/rejected; survives worker restarts |
| **Long-term: episodic** | Raw messages + segments, embedded and full-text indexed | `messages`, `segments` (pgvector `embedding`, GIN `tsv`) | Permanent |
| **Long-term: semantic** | Structured items + audit trail, entity profiles | `items`, `item_evidence`, `item_history`, `entities` | Updated per batch, refreshed nightly |
| **Long-term: summaries** | Daily and weekly per-chat rollups | `summaries` (embedded) | Nightly consolidation |
| **Procedural** | Escalation rule thresholds | `rules` (Settings page, `services/rules.py`) | On change |

## Retrieval: hybrid search + RRF (`memory/retrieval.py`)

`hybrid_search(session, query, embedder, k, chat_id=None)` runs two independent rankings over `messages` and fuses them:

1. **Vector**: pgvector cosine distance against `embedding`, using the configured embedding provider (`bge-m3` via Ollama by default, multilingual so Bangla/Banglish and English queries all work; a deterministic Fake provider for tests).
2. **Full-text**: Postgres `to_tsvector('simple', text)` / `plainto_tsquery('simple', query)`. The `simple` config (not `english`) is deliberate — English stemming mangles Bangla script and romanized Banglish tokens, which would silently break search for a large share of the sample chats.
3. **Fusion**: **Reciprocal Rank Fusion**, `score = Σ 1/(RRF_K + rank + 1)` across both rankings (`RRF_K = 60`), rather than trying to normalize and blend two very different score distributions.

Each `SearchResult` carries `message_id`, `chat_id`, and the message text, so every citation the Assistant Agent produces traces back to a concrete row — the reflection step in `agents/assistant.py` checks exactly this.

## Consolidation job (`memory/consolidation.py`, nightly ARQ cron at 02:00 Asia/Dhaka)

- Groups non-system messages by chat and calendar day, builds/updates a daily `Summary` per chat, then rolls days into a weekly `Summary`. Upserts are idempotent (skipped if the computed text is unchanged) and re-embed only on an actual change, so re-running the job is cheap.
- Refreshes each participant's linked `Entity` profile (`kind="person"`) with their current non-done/cancelled items.
- Marks items with no `updated_at` change in 14 days as `validation_status="needs_review"`, so stale-but-still-open items resurface in the Review Queue instead of silently rotting.

## Why Postgres for everything

One datastore serves relational state, vector search, full-text search, and LangGraph's checkpoint tables (`langgraph-checkpoint-postgres`). This keeps local setup to a single `docker compose up`, keeps the Action Agent's approval-pause durable without a second stateful service, and lets hybrid search join directly against `chats`/`items` for filtering without a cross-database round trip.
