# Demo Script (5–7 minutes)

## Setup (before recording)

```
cp .env.example .env      # or `make env`
make up                   # postgres, redis, mailpit, backend, worker, frontend
make seed                 # demo users + ingest data/sample/exports + run the pipeline + monitor + plan actions
```

Demo credentials: **manager@demo.local** / **analyst@demo.local**, password `demo1234` for both.

Frontend: http://localhost:3000 · API docs: http://localhost:8000/docs · Mailpit: http://localhost:8025

## 1. Ingestion is real, not a mock (45s)

Log in as **manager@demo.local**. Open **Ingestion**. Point out the 5 chats already listed (seeded from committed Android `.txt` / iOS `.zip` exports under `data/sample/exports/`) — this is real WhatsApp export parsing, not synthetic rows inserted directly into the database. Optionally re-upload one export to show the "N imported · N duplicates" idempotency message.

*(Optional, if you want to show the Cloud API path too: `make simulate-webhook` in a terminal — replays signed fixtures against `POST /api/webhook`, and the resulting chat/messages appear in Chat Explorer within one pipeline cycle.)*

## 2. Extraction with evidence (60s)

Open **Chat Explorer**, pick **Project Padma Warehouse**. Scroll to a message like *"Nadia, can you confirm the racking delivery kal?"* and show the extracted **action** item next to it: owner `Nadia`, due date resolved from "kal" (Bangla for "tomorrow") to an actual date. Click through to **Actions**, open the evidence drawer on that item — the quoted evidence links back to the exact source message.

## 3. The agent loop is visible, not just claimed (60s)

Open **Agent activity**. Filter to `agent=pipeline`. Point at a segment with more than one `analyse` iteration: the first `validate` failed (e.g. an ungrounded quote or an unresolved owner), the feedback was fed back to the Analyst, and the second `analyse` produced a passing extraction. This is the Analyst⇄Validator retry loop actually firing, logged end-to-end — not a diagram.

## 4. Escalations and the human approval gate (90s)

Open **Escalations**. Show a planted scenario firing correctly, e.g. the recurring-issue detector on Ops & Incidents (raised 3+ times in 7 days) or the unowned-high-risk detector. Open **Approvals**, find a pending outbound action, click to preview the drafted message, then **Approve** as the manager. Switch to Mailpit (or the Agent Activity feed for a WhatsApp `simulated` send) and show the message actually went out — the approval resumed a paused LangGraph run, it didn't just flip a status flag.

Log out, log in as **analyst@demo.local**, and show the Approve button is gone / a direct API call is rejected with 403 — RBAC is enforced, not cosmetic.

## 5. Search across languages (45s)

Open **Search** (back as manager, or stay as analyst). Run one English query and one Bangla/Banglish query (e.g. "porshu" or a Bangla phrase from Ops & Incidents) and show both return relevant messages — hybrid vector + full-text search with the `simple` text-search config, not English-only.

## 6. The management assistant, with citations (90s)

Open **AI assistant**. Ask *"What's overdue and who owns it?"* — show the answer cites specific messages (clickable citation chips) rather than a generic summary. Ask a follow-up in the same thread to show conversation memory. If time allows, ask something the data can't support and show the assistant says so instead of inventing an answer — the citation-validation/reflection step at work.

## 7. Close (30s)

Back to **Overview**: KPI cards and trend charts, live from the same data just walked through. One sentence: "Every number on this page, every extracted item, and every agent decision traces back to a real source message — that traceability is the point."

## If asked "what's simulated vs. real"

- Real: export parsing, segmentation, LLM extraction (when `LLM_PROVIDER=anthropic`/`ollama`), the validator retry loop, escalation detection, RBAC-gated approval with a durable pause/resume, hybrid search, assistant citations.
- Simulated by default (config-flip to go live, no code change): outbound email (`EMAIL_MODE=smtp` + real SMTP), WhatsApp send (`WHATSAPP_MODE=live` + a real Meta Cloud API app/token), and — unless an Anthropic key is set — the LLM itself falls back to a small deterministic rule-based extractor (`app/llm/demo_provider.py`) so the whole demo runs with zero API keys.
