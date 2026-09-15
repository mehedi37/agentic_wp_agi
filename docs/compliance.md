# Compliance

## Ingestion channels and consent

- **Export Chat (primary path).** WhatsApp's own "Export Chat" feature is used by a participant of the conversation, with the group/chat's understanding that its content is being captured for business record-keeping — the same basis under which a manager already screenshots or forwards WhatsApp content for work purposes today. No unofficial automation (whatsapp-web.js, Baileys, or any approach that impersonates the WhatsApp client) is used anywhere in this project, because that class of tool operates outside WhatsApp's Terms of Service.
- **WhatsApp Business Cloud API (secondary path, `docs/architecture.md` §1).** This is Meta's own official, contractual integration point — messages only flow through it for numbers the business has onboarded to its own WhatsApp Business Account, i.e. conversations the business is already a first-party participant in.
- **WhatsApp Channels** have no official export or public API for reading channel posts. The only supported workaround is a channel admin forwarding posts into a monitored business chat/number, which then ingests through the two paths above. This is a documented limitation, not a supported integration.

## Data minimization and storage

- **Phone numbers are never stored raw.** `participants.phone_hash` is a SHA-256 hash and `phone_masked` keeps only the last 4 digits (e.g. `••••0021`); the UI and API never surface a full number. Cloud API chat identity (`chats.external_id`) is itself a hash of `business_number|customer_number`, so even the join key isn't a plaintext number.
- **Retention** is a deployment-time decision (no automatic purge is built in for the demo); the schema is structured so a retention job can filter on `messages.ts` / `chats.created_at` without touching any other table, and would only need to add one scheduled deletion job.
- **Audit log.** `audit_log` records who changed what (currently: Monitor rule threshold changes via Settings); `item_history` records every item status change with its actor. Both are additive/append-only.

## LLM data usage

- The LLM provider is configurable per `LLM_PROVIDER` (`llm/factory.py`): **Claude** (Anthropic API — see Anthropic's data usage policy for API traffic, which is not used for model training by default), **Ollama** (fully local, nothing leaves the machine), or **Fake/Demo** (a deterministic, non-LLM rule-based extractor — no external call at all, used by default and in every test).
- Segment text sent to the LLM is the conversation content itself (needed to extract items and answer questions); no phone numbers are ever included in a prompt, since participants are only referenced by `display_name` after the hashing/masking step above.
- A fully local deployment (`docker compose --profile local-llm up`, `LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=ollama`) keeps conversation content on-premises end to end, for organizations that cannot send chat content to a third-party API at all.

## Outbound messaging

- Every outbound action (email or WhatsApp reply) passes through the Action Agent's approval gate (`docs/agents.md` §3) — nothing is sent automatically. A manager sees the drafted message before it goes out.
- `EMAIL_MODE` / `WHATSAPP_MODE` default to `simulated`: sends are recorded (visible in the dashboard/Agent Activity) but nothing actually leaves the system, which is what the demo and CI run against. Setting them to `smtp` / `live` (plus real credentials) switches to genuinely sending, with no code change.
