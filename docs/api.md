# API Reference

Base path: `/api`. Interactive OpenAPI docs are served at `/docs` (Swagger UI) whenever the backend is running. Every route below except `GET /health` and the two `webhook` routes requires a JWT (`Authorization: Bearer <token>` from `POST /api/auth/login`).

## Auth

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/auth/login` | — | `{email, password}` → `{access_token, token_type}` |
| GET | `/auth/me` | any | current user's id/email/role |

## Ingestion

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/ingest/upload` | analyst, manager | multipart: `chat_name`, `date_order`, `file` (.txt/.zip); dedupes by content hash, enqueues `process_batch` |
| GET | `/ingest/jobs` | any | recent ingestion job status |
| POST | `/chats/{chat_id}/process` | any | manually re-enqueue processing (retry) |
| GET | `/webhook` | — | Meta `hub.verify_token` handshake |
| POST | `/webhook` | — (HMAC-signed) | `X-Hub-Signature-256` verified against `WHATSAPP_APP_SECRET`; 401 on a bad signature, 422 on a malformed-but-signed payload |

## Read / search

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/chats` | any | list chats |
| GET | `/chats/{chat_id}/messages` | any | `limit` (default 200) |
| GET | `/messages/{message_id}` | any | single message, for citation drill-down |
| GET | `/items` | any | filters: `item_type`, `item_status`, `chat_id`, `owner_participant_id`, `overdue` |
| GET | `/items/{item_id}/evidence` | any | the cited messages behind one item |
| PATCH | `/items/{item_id}/status` | any | body `{"new_status": ...}`; writes an `item_history` row (`actor="user"`) |
| GET | `/escalations` | any | filter: `escalation_status` |
| GET | `/dashboard/metrics` | any | open/overdue actions, new risks (7d), decisions (7d), open escalations, pending approvals |
| GET | `/search` | any | `q`, `k`, optional `chat_id`; hybrid (vector + full-text) search with RRF |
| GET | `/agent-runs` | any | Agent Activity feed |

## Actions (approval gate)

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/actions` | any | list, filterable by status |
| POST | `/actions/{action_id}/approve` | **manager** | resumes the paused LangGraph run; 409 if not pending |
| POST | `/actions/{action_id}/reject` | **manager** | optional `{"feedback": ...}`, stored, never executed |

## Assistant

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/assistant/chat` | any | `{question, thread_id?, stream?}`; `stream: true` returns `text/event-stream`; every answer includes `citations` and a `grounded` flag |

## Settings

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/settings/rules` | **manager** | current Monitor detector thresholds |
| PUT | `/settings/rules/{key}` | **manager** | `{enabled, params}`; params must be known keys, values 1–365; recorded to `audit_log` |

## Health

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness probe used by the Docker Compose healthcheck |
