# Phase 0: Foundations & Contracts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the runnable project skeleton (Docker Compose stack, backend package, frontend app), the database schema, the shared Pydantic contracts, the pluggable LLM/embedding provider layer, and JWT auth with RBAC — the four contracts every later phase of the Agentic WhatsApp Intelligence & Management Dashboard builds on.

**Architecture:** Python 3.12 FastAPI backend (uv-managed) with SQLAlchemy 2 + Alembic against Postgres 16 + pgvector, Redis for the job queue, a Next.js (TypeScript, App Router) frontend, all orchestrated by Docker Compose. Tasks in this phase are intentionally sequential (each defines a contract the next needs) except T0.4 and T0.5, which can run in parallel once T0.2/T0.3 land.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pydantic-settings, Postgres 16 + pgvector, Redis, ARQ, Anthropic SDK, Ollama (HTTP), pytest, Next.js 14+ (App Router, TypeScript), Tailwind CSS, Docker Compose, uv, ruff, mypy, bcrypt (via `passlib[bcrypt]` or `bcrypt` directly), `python-jose` for JWT.

**Spec:** `PLAN.md` (repo root) — sections 2–5, 8, 13 (Phase 0 row).

## Global Constraints

- Never mention "Anthropic", "Claude", "Co-Authored-By", or any AI-attribution text in commit messages, code comments, docs, or anywhere else in this repository. Commit messages are plain, describing only the change.
- Backend package manager is **uv**; do not use pip/poetry/conda directly. All backend commands run through `uv run ...`.
- Python version floor: **3.12**. Node version floor: **20**.
- All backend code is typed; `mypy` must pass with no errors on the `app/` package. All backend code is linted with `ruff` (default rule set) with no errors.
- All service ports and container names are exactly as given in Task 0.1 — later phases' docs and scripts assume them.
- Database: Postgres 16 with the `vector` extension (pgvector). Embedding dimension is **1024** everywhere (matches `bge-m3`).
- Timezone for date logic is **Asia/Dhaka**; store all timestamps in the database as UTC (`TIMESTAMPTZ`).
- API prefix is `/api`. Auth uses JWT bearer tokens (`Authorization: Bearer <token>`), HS256, secret from `settings.jwt_secret`, access-token TTL 12 hours.
- Two roles only: `manager` and `analyst`. Role values are the literal lowercase strings `"manager"` and `"analyst"` everywhere (enum, DB column, JWT claim, API responses).
- Demo seed users: `manager@demo.local` / `analyst@demo.local`, both password `demo1234` (documented in README, seeded by `scripts/seed.py`, not created in this phase — see T0.5's seed helper only).
- Every FastAPI route file lives under `backend/app/api/routes/`; every route is registered in `backend/app/main.py` via an `APIRouter` include — no route wiring anywhere else.
- No task in this phase calls a real external LLM API in its automated tests. Tests exercise the `FakeProvider` only. A real Anthropic/Ollama call is allowed only behind a manual, skipped-by-default smoke test.

---

## File Structure

```
agentic_wp_agi/
├── docker-compose.yml
├── Makefile
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial_schema.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── message.py
│   │   │   ├── item.py
│   │   │   ├── escalation.py
│   │   │   ├── action.py
│   │   │   └── auth.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── fake_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── ollama_provider.py
│   │   │   ├── embeddings.py
│   │   │   └── factory.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── deps.py
│   │       └── routes/
│   │           ├── __init__.py
│   │           ├── health.py
│   │           └── auth.py
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       ├── db/test_models.py
│       ├── llm/test_fake_provider.py
│       ├── llm/test_factory.py
│       └── api/test_auth.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── Dockerfile
│   └── app/
│       ├── layout.tsx
│       ├── page.tsx
│       └── globals.css
└── scripts/
    └── wait_for_services.sh
```

Each backend module has one job: `core/` is config and security primitives, `db/` is persistence, `schemas/` is the Pydantic contract layer every route/agent imports, `llm/` is the provider abstraction, `api/` is HTTP wiring only (no business logic lives in a route function beyond calling into services — services arrive in later phases).

---

## Task 1: Repo Scaffold, Docker Compose & Tooling

**Files:**
- Create: `docker-compose.yml`, `Makefile`, `.env.example`, `.dockerignore`
- Create: `backend/pyproject.toml`, `backend/Dockerfile`, `backend/app/__init__.py`, `backend/app/main.py`
- Create: `backend/app/api/__init__.py`, `backend/app/api/routes/__init__.py`, `backend/app/api/routes/health.py`
- Create: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.mjs`, `frontend/tailwind.config.ts`, `frontend/postcss.config.mjs`, `frontend/Dockerfile`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/app/globals.css`
- Create: `scripts/wait_for_services.sh`

**Interfaces:**
- Produces: a running `docker compose up` stack with services named exactly `postgres`, `redis`, `mailpit`, `backend`, `frontend` (an `ollama` service is optional, under Compose profile `local-llm`, but is not required to pass this task).
- Produces: `GET /api/health` returning `{"status": "ok"}` with HTTP 200.
- Produces: `Makefile` targets `up`, `down`, `logs`, `lint`, `test`, `fmt` that later tasks may extend but must not rename.
- Produces: backend `pyproject.toml` with dependency groups later tasks add to (do not pin a dependency here that a later task must re-pin differently).

- [ ] **Step 1: Write `.env.example`**

```
# --- Postgres ---
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_DB=agentic_wp
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://app:app@postgres:5432/agentic_wp

# --- Redis ---
REDIS_URL=redis://redis:6379/0

# --- Auth ---
JWT_SECRET=dev-secret-change-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_TTL_HOURS=12

# --- LLM ---
LLM_PROVIDER=fake
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5
ANTHROPIC_FAST_MODEL=claude-haiku-4-5-20251001
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024

# --- Mail ---
SMTP_HOST=mailpit
SMTP_PORT=1025

# --- WhatsApp Cloud API ---
WHATSAPP_MODE=simulated
WHATSAPP_VERIFY_TOKEN=dev-verify-token
WHATSAPP_APP_SECRET=dev-app-secret
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=

# --- App ---
APP_TIMEZONE=Asia/Dhaka
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: agentic_wp_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-app}
      POSTGRES_DB: ${POSTGRES_DB:-agentic_wp}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app} -d ${POSTGRES_DB:-agentic_wp}"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: agentic_wp_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  mailpit:
    image: axllent/mailpit:latest
    container_name: agentic_wp_mailpit
    restart: unless-stopped
    ports:
      - "8025:8025"
      - "1025:1025"

  backend:
    build:
      context: ./backend
    container_name: agentic_wp_backend
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  frontend:
    build:
      context: ./frontend
    container_name: agentic_wp_frontend
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000/api
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    command: ["npm", "run", "dev"]

  ollama:
    image: ollama/ollama:latest
    container_name: agentic_wp_ollama
    restart: unless-stopped
    profiles: ["local-llm"]
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  pgdata:
  ollama_data:
```

- [ ] **Step 3: Write `.dockerignore`**

```
.git
.venv
__pycache__
node_modules
.next
*.pyc
.superpowers
```

- [ ] **Step 4: Write `Makefile`**

```makefile
.PHONY: up down logs lint test fmt seed eval

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	cd backend && uv run ruff check app && uv run mypy app
	cd frontend && npm run lint

fmt:
	cd backend && uv run ruff format app tests

test:
	cd backend && uv run pytest -q

seed:
	cd backend && uv run python -m scripts.seed

eval:
	cd backend && uv run python -m scripts.run_eval
```

- [ ] **Step 5: Write `backend/pyproject.toml`**

```toml
[project]
name = "agentic-wp-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
    "alembic>=1.14",
    "psycopg[binary]>=3.2",
    "pgvector>=0.3.6",
    "redis>=5.2",
    "arq>=0.26",
    "python-jose[cryptography]>=3.3",
    "bcrypt>=4.2",
    "anthropic>=0.40",
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "ruff>=0.7",
    "mypy>=1.13",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
disallow_untyped_defs = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 6: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY . .
RUN uv sync

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Write `backend/app/__init__.py`** (empty file)

- [ ] **Step 8: Write `backend/app/api/routes/health.py`**

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 9: Write `backend/app/api/routes/__init__.py`** (empty file) and `backend/app/api/__init__.py` (empty file)

- [ ] **Step 10: Write `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(title="Agentic WhatsApp Intelligence & Management Dashboard")

app.include_router(health.router, prefix="/api")
```

- [ ] **Step 11: Write `backend/tests/__init__.py`** (empty file) and `backend/tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
```

- [ ] **Step 12: Write the failing test `backend/tests/test_health.py`**

```python
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 13: Install deps and run the test to verify behavior**

Run: `cd backend && uv sync --group dev && uv run pytest tests/test_health.py -v`
Expected: PASS (1 passed)

- [ ] **Step 14: Scaffold the Next.js frontend**

`frontend/package.json`:

```json
{
  "name": "agentic-wp-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.15",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "20.16.11",
    "@types/react": "18.3.11",
    "@types/react-dom": "18.3.1",
    "tailwindcss": "3.4.13",
    "postcss": "8.4.47",
    "autoprefixer": "10.4.20",
    "eslint": "8.57.1",
    "eslint-config-next": "14.2.15"
  }
}
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

`frontend/next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {};

export default nextConfig;
```

`frontend/tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};

export default config;
```

`frontend/postcss.config.mjs`:

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

`frontend/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`frontend/app/layout.tsx`:

```tsx
import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Agentic WhatsApp Intelligence & Management Dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

`frontend/app/page.tsx`:

```tsx
export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <h1 className="text-2xl font-semibold">Agentic WhatsApp Intelligence & Management Dashboard</h1>
    </main>
  );
}
```

`frontend/Dockerfile`:

```dockerfile
FROM node:20-slim

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
```

- [ ] **Step 15: Write `scripts/wait_for_services.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for backend health endpoint..."
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/health > /dev/null; then
    echo "Backend is healthy."
    exit 0
  fi
  sleep 2
done

echo "Backend did not become healthy in time." >&2
exit 1
```

Run: `chmod +x scripts/wait_for_services.sh`

- [ ] **Step 16: Bring the stack up and verify end to end**

Run: `docker compose up -d --build postgres redis mailpit backend frontend`
Run: `bash scripts/wait_for_services.sh`
Run: `curl -s http://localhost:8000/api/health`
Expected: `{"status":"ok"}`
Run: `curl -sI http://localhost:3000 | head -1`
Expected: `HTTP/1.1 200 OK`
Run: `docker compose down`

- [ ] **Step 17: Commit**

```bash
git add docker-compose.yml Makefile .env.example .dockerignore backend frontend scripts
git commit -m "chore: scaffold docker compose stack, backend skeleton, frontend skeleton"
```

---

## Task 2: Database Models & Alembic Migration

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/db/models.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial_schema.py`
- Create: `backend/tests/db/__init__.py`, `backend/tests/db/test_models.py`
- Modify: `backend/pyproject.toml` (no new deps needed; already listed in T0.1)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `app.core.config.Settings` (a `pydantic_settings.BaseSettings` subclass) and a module-level `settings = Settings()` singleton that every later task imports for config (`settings.database_url`, `settings.jwt_secret`, `settings.jwt_algorithm`, `settings.jwt_access_token_ttl_hours`, `settings.llm_provider`, `settings.anthropic_api_key`, `settings.anthropic_model`, `settings.anthropic_fast_model`, `settings.ollama_base_url`, `settings.ollama_model`, `settings.embedding_provider`, `settings.embedding_model`, `settings.embedding_dim`, `settings.app_timezone`, `settings.smtp_host`, `settings.smtp_port`, `settings.whatsapp_mode`, `settings.whatsapp_verify_token`, `settings.whatsapp_app_secret`, `settings.whatsapp_phone_number_id`, `settings.whatsapp_access_token`).
- Produces: `app.db.session.get_session` — a FastAPI dependency (`Generator[Session, None, None]`) yielding a SQLAlchemy `Session` bound to `settings.database_url`, and `app.db.session.SessionLocal` (a `sessionmaker`) for non-request use (workers, scripts).
- Produces: `app.db.base.Base` — the `DeclarativeBase` every ORM model inherits from.
- Produces ORM models in `app.db.models`: `User`, `Chat`, `Participant`, `Message`, `Segment`, `Item`, `ItemEvidence`, `ItemHistory`, `Entity`, `EntityMention`, `Summary`, `Escalation`, `ProposedAction`, `Notification`, `AgentRun`, `IngestionJob`, `Rule`, `Feedback`, `AuditLog` — exact columns below. All PKs are `uuid.UUID` (server default `gen_random_uuid()`, requires the `pgcrypto` extension). All `created_at`/`updated_at` columns are `TIMESTAMPTZ` with `server_default=func.now()`.

- [ ] **Step 1: Write `backend/app/core/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/agentic_wp"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_hours: int = 12

    llm_provider: str = "fake"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    anthropic_fast_model: str = "claude-haiku-4-5-20251001"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    smtp_host: str = "localhost"
    smtp_port: int = 1025

    whatsapp_mode: str = "simulated"
    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_app_secret: str = "dev-app-secret"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    app_timezone: str = "Asia/Dhaka"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 2: Write `backend/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 3: Write `backend/app/db/session.py`**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 4: Write `backend/app/db/models.py`**

```python
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base

EMBED_DIM = settings.embedding_dim


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # "manager" | "analyst"
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(Text, nullable=False)  # "export" | "cloud_api"
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # "group" | "direct" | "channel"
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Asia/Dhaka")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    participants: Mapped[list["Participant"]] = relationship(back_populates="chat")


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )

    chat: Mapped["Chat"] = relationship(back_populates="participants")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_messages_content_hash"),
        Index("ix_messages_chat_ts", "chat_id", "ts"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    source_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    lang: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False)
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    start_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    message_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    analysis_status: Mapped[str] = mapped_column(Text, default="pending")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[str] = mapped_column(Text, nullable=False)  # action|decision|risk|issue
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("segments.id", ondelete="SET NULL"), nullable=True
    )
    owner_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    owner_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    due_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="open")
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    likelihood: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    validation_status: Mapped[str] = mapped_column(Text, default="pending")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ItemEvidence(Base):
    __tablename__ = "item_evidence"

    id: Mapped[uuid.UUID] = _uuid_pk()
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    quote: Mapped[str] = mapped_column(Text, nullable=False)


class ItemHistory(Base):
    __tablename__ = "item_history"

    id: Mapped[uuid.UUID] = _uuid_pk()
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    change: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)  # "agent" | "user"
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # person|project|client|topic
    name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scope: Mapped[str] = mapped_column(Text, nullable=False)  # chat|project|person|day|week|month
    scope_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL"), nullable=True
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="open")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class ProposedAction(Base):
    __tablename__ = "proposed_actions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    escalation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("escalations.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # notify|email|whatsapp|status_update
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    edit: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent: Mapped[str] = mapped_column(Text, nullable=False)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    iteration: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending")
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Add alembic and psycopg dev tooling, init alembic**

Run: `cd backend && uv sync --group dev`
Run: `cd backend && uv run alembic init alembic`

- [ ] **Step 6: Rewrite `backend/alembic.ini`'s `sqlalchemy.url` line to be blank (env.py sets it from settings)**

Edit the generated `backend/alembic.ini`: set `sqlalchemy.url =` (empty — do not hardcode a DSN there).

- [ ] **Step 7: Write `backend/alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (ensures models are registered on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Generate the initial migration**

Run: `cd backend && docker compose up -d postgres` (from repo root, or point `DATABASE_URL` at any reachable Postgres 16 with pgvector)
Run: `cd backend && uv run python -c "from sqlalchemy import create_engine, text; from app.core.config import settings; e=create_engine(settings.database_url); e.connect().execute(text('CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto')).connection.commit()"`
Run: `cd backend && uv run alembic revision --autogenerate -m "initial schema"`
Rename the generated file under `backend/alembic/versions/` to `0001_initial_schema.py` (keep its revision id as generated; only the filename changes).

Manually edit the generated migration's `upgrade()` to insert, as the very first statements, the extension creation (autogenerate does not emit these):

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    # ... (rest of the autogenerated op.create_table(...) calls follow, unchanged)
```

- [ ] **Step 9: Apply the migration and verify**

Run: `cd backend && uv run alembic upgrade head`
Expected: no errors; exits 0.
Run: `cd backend && uv run python -c "from sqlalchemy import create_engine, inspect; from app.core.config import settings; print(sorted(inspect(create_engine(settings.database_url)).get_table_names()))"`
Expected: a sorted list containing all 18 table names from Step 4 plus `alembic_version`.

- [ ] **Step 10: Write `backend/tests/db/__init__.py`** (empty file) and `backend/tests/db/test_models.py`

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Chat, Message, User


def _engine():
    return create_engine(settings.database_url)


def test_user_role_roundtrip() -> None:
    engine = _engine()
    with Session(engine) as session:
        user = User(
            email=f"test-{uuid.uuid4()}@example.com",
            name="Test User",
            role="manager",
            password_hash="x",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        assert user.role == "manager"
        session.delete(user)
        session.commit()


def test_message_content_hash_unique() -> None:
    engine = _engine()
    with Session(engine) as session:
        chat = Chat(source="export", name="Test Chat", type="group", timezone="Asia/Dhaka")
        session.add(chat)
        session.commit()
        session.refresh(chat)

        content_hash = f"hash-{uuid.uuid4()}"
        msg = Message(
            chat_id=chat.id,
            ts=datetime.now(timezone.utc),
            text="hello",
            content_hash=content_hash,
        )
        session.add(msg)
        session.commit()

        dup = Message(
            chat_id=chat.id,
            ts=datetime.now(timezone.utc),
            text="hello again",
            content_hash=content_hash,
        )
        session.add(dup)
        try:
            session.commit()
            raised = False
        except Exception:
            session.rollback()
            raised = True
        assert raised, "duplicate content_hash must violate the unique constraint"

        session.delete(msg)
        session.delete(chat)
        session.commit()
```

- [ ] **Step 11: Run the tests to verify they pass against the migrated database**

Run: `cd backend && uv run pytest tests/db/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 12: Commit**

```bash
git add backend/app/core backend/app/db backend/alembic.ini backend/alembic backend/tests/db backend/pyproject.toml
git commit -m "feat: add settings, db session, orm models, initial alembic migration"
```

---

## Task 3: Shared Pydantic Contracts

**Files:**
- Create: `backend/app/schemas/__init__.py`, `backend/app/schemas/enums.py`, `backend/app/schemas/message.py`, `backend/app/schemas/item.py`, `backend/app/schemas/escalation.py`, `backend/app/schemas/action.py`, `backend/app/schemas/auth.py`
- Create: `backend/tests/schemas/__init__.py`, `backend/tests/schemas/test_item.py`, `backend/tests/schemas/test_message.py`

**Interfaces:**
- Consumes: nothing (pure Pydantic, no DB/ORM imports — this is deliberate: `schemas/` must stay importable without a database connection, since later phases import it into agents, workers and the frontend's OpenAPI generation).
- Produces: `app.schemas.enums.ItemType` (`Literal["action", "decision", "risk", "issue"]`), `ItemStatus` (`Literal["open", "in_progress", "done", "cancelled", "needs_review"]`), `Role` (`Literal["manager", "analyst"]`), `EscalationStatus` (`Literal["open", "acknowledged", "resolved", "auto_closed"]`), `ActionKind` (`Literal["notify", "email", "whatsapp", "status_update"]`), `ActionStatus` (`Literal["pending", "approved", "rejected", "executing", "executed", "failed"]`).
- Produces: `app.schemas.message.MessageIn`, `MessageOut` (fields matching the `messages` table from T0.2, `id`/`chat_id`/`participant_id` typed `uuid.UUID`, `ts` typed `datetime`).
- Produces: `app.schemas.item.EvidenceRef {message_id: uuid.UUID, quote: str}`, `ExtractedItem {type: ItemType, title: str, description: str | None, owner_raw: str | None, owner_participant_id: uuid.UUID | None, due_date_raw: str | None, due_at: datetime | None, priority: str | None, severity: str | None, likelihood: str | None, status_hint: Literal["new","update","completed","cancelled"], related_item_id: uuid.UUID | None, evidence: list[EvidenceRef], confidence: float}` with a field validator that rejects `confidence` outside `[0.0, 1.0]`, and `ItemOut` (adds `id`, `chat_id`, `status: ItemStatus`, `created_at`, `updated_at`).
- Produces: `app.schemas.escalation.EscalationOut {id, rule: str, severity: str, item_id: uuid.UUID | None, chat_id: uuid.UUID | None, rationale: str, evidence: dict | None, status: EscalationStatus, created_at: datetime}`.
- Produces: `app.schemas.action.ProposedActionOut {id, escalation_id: uuid.UUID | None, kind: ActionKind, payload: dict, status: ActionStatus, decided_by: uuid.UUID | None, decided_at: datetime | None, result: dict | None, created_at: datetime}`.
- Produces: `app.schemas.auth.LoginRequest {email: EmailStr, password: str}`, `TokenResponse {access_token: str, token_type: Literal["bearer"], role: Role, name: str}`, `CurrentUser {id: uuid.UUID, email: str, name: str, role: Role}`.
- All schemas use `model_config = ConfigDict(from_attributes=True)` so they build directly from ORM instances.

- [ ] **Step 1: Write `backend/app/schemas/enums.py`**

```python
from typing import Literal

ItemType = Literal["action", "decision", "risk", "issue"]
ItemStatus = Literal["open", "in_progress", "done", "cancelled", "needs_review"]
Role = Literal["manager", "analyst"]
EscalationStatus = Literal["open", "acknowledged", "resolved", "auto_closed"]
ActionKind = Literal["notify", "email", "whatsapp", "status_update"]
ActionStatus = Literal["pending", "approved", "rejected", "executing", "executed", "failed"]
StatusHint = Literal["new", "update", "completed", "cancelled"]
```

- [ ] **Step 2: Write `backend/app/schemas/message.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageIn(BaseModel):
    chat_id: uuid.UUID
    participant_id: uuid.UUID | None = None
    source_message_id: str | None = None
    ts: datetime
    text: str
    lang: str | None = None
    media_type: str | None = None
    is_system: bool = False
    reply_to_id: uuid.UUID | None = None
    raw: dict | None = None
    content_hash: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: uuid.UUID
    participant_id: uuid.UUID | None
    source_message_id: str | None
    ts: datetime
    text: str
    text_normalized: str | None
    lang: str | None
    media_type: str | None
    is_system: bool
    reply_to_id: uuid.UUID | None
    content_hash: str
```

- [ ] **Step 3: Write `backend/app/schemas/item.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import ItemStatus, ItemType, StatusHint


class EvidenceRef(BaseModel):
    message_id: uuid.UUID
    quote: str


class ExtractedItem(BaseModel):
    type: ItemType
    title: str
    description: str | None = None
    owner_raw: str | None = None
    owner_participant_id: uuid.UUID | None = None
    due_date_raw: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    severity: str | None = None
    likelihood: str | None = None
    status_hint: StatusHint = "new"
    related_item_id: uuid.UUID | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ItemType
    title: str
    description: str | None
    chat_id: uuid.UUID
    owner_participant_id: uuid.UUID | None
    owner_raw: str | None
    due_at: datetime | None
    due_raw: str | None
    status: ItemStatus
    priority: str | None
    severity: str | None
    likelihood: str | None
    confidence: float | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Write `backend/app/schemas/escalation.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import EscalationStatus


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule: str
    severity: str
    item_id: uuid.UUID | None
    chat_id: uuid.UUID | None
    rationale: str
    evidence: dict | None
    status: EscalationStatus
    created_at: datetime
```

- [ ] **Step 5: Write `backend/app/schemas/action.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import ActionKind, ActionStatus


class ProposedActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    escalation_id: uuid.UUID | None
    kind: ActionKind
    payload: dict
    status: ActionStatus
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    result: dict | None
    created_at: datetime
```

- [ ] **Step 6: Write `backend/app/schemas/auth.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.enums import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    name: str


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: Role
```

- [ ] **Step 7: Write `backend/app/schemas/__init__.py`** (empty file)

- [ ] **Step 8: Write the tests `backend/tests/schemas/__init__.py`** (empty file) and `backend/tests/schemas/test_item.py`

```python
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
```

- [ ] **Step 9: Write `backend/tests/schemas/test_message.py`**

```python
import uuid
from datetime import datetime, timezone

from app.schemas.message import MessageIn


def test_message_in_builds_from_minimal_fields() -> None:
    msg = MessageIn(
        chat_id=uuid.uuid4(),
        ts=datetime.now(timezone.utc),
        text="hello",
        content_hash="abc123",
    )
    assert msg.is_system is False
    assert msg.participant_id is None
```

- [ ] **Step 10: Run the tests**

Run: `cd backend && uv run pytest tests/schemas -v`
Expected: PASS (3 passed)

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas backend/tests/schemas
git commit -m "feat: add shared pydantic contracts for messages, items, escalations, actions, auth"
```

---

## Task 4: LLM & Embedding Provider Layer

**Files:**
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/base.py`, `backend/app/llm/fake_provider.py`, `backend/app/llm/anthropic_provider.py`, `backend/app/llm/ollama_provider.py`, `backend/app/llm/embeddings.py`, `backend/app/llm/factory.py`
- Create: `backend/tests/llm/__init__.py`, `backend/tests/llm/test_fake_provider.py`, `backend/tests/llm/test_factory.py`

**Interfaces:**
- Consumes: `app.core.config.settings` (T0.2).
- Produces: `app.llm.base.LLMProvider` — an abstract base class every provider implements:
  ```python
  class LLMProvider(ABC):
      name: str
      @abstractmethod
      async def chat(self, messages: list[ChatMessage], *, system: str | None = None, model: str | None = None, temperature: float = 0.2) -> ChatResult: ...
      @abstractmethod
      async def structured(self, messages: list[ChatMessage], *, response_model: type[BaseModelT], system: str | None = None, model: str | None = None) -> BaseModelT: ...
      @abstractmethod
      async def tool_loop(self, messages: list[ChatMessage], *, tools: list[ToolSpec], tool_executor: ToolExecutor, system: str | None = None, model: str | None = None, max_steps: int = 8) -> ChatResult: ...
  ```
  where `ChatMessage = TypedDict("ChatMessage", {"role": Literal["user","assistant"], "content": str})`, `ChatResult` is a dataclass `{text: str, tokens_in: int, tokens_out: int, model: str, tool_calls: list[ToolCallRecord]}`, `ToolSpec` is a dataclass `{name: str, description: str, input_schema: dict}`, `ToolExecutor` is `Callable[[str, dict], Awaitable[str]]` (tool name, tool input JSON → tool result string), `ToolCallRecord` is a dataclass `{name: str, input: dict, output: str}`, `BaseModelT` is a `TypeVar` bound to `pydantic.BaseModel`.
- Produces: `app.llm.fake_provider.FakeProvider(LLMProvider)` — deterministic, script-driven: constructed as `FakeProvider(responses: list[str] | None = None, structured_responses: list[BaseModel] | None = None)`. `chat()` pops and returns the next scripted text response (cycling if the script is shorter than the number of calls; if no script given, echoes the last user message content prefixed with `"FAKE: "`). `structured()` pops and returns the next scripted structured response, `model_validate`-ing it into `response_model` if it's a dict, or returning it directly if it's already an instance of `response_model`. `tool_loop()` returns a `ChatResult` with `text` from the next scripted chat response and empty `tool_calls` (Task 2.3's assistant tests script tool interactions at a higher level using `tool_executor` directly, not through this method — this base capability is enough for Phase 0/1 needs). Every call increments `self.call_count` and appends the call's inputs to `self.calls` (a list) so tests can assert on what was sent.
- Produces: `app.llm.anthropic_provider.AnthropicProvider(LLMProvider)` — wraps the `anthropic` SDK's `AsyncAnthropic` client; `chat()` calls `messages.create`; `structured()` uses tool-forced structured output (a single tool named `emit_result` whose `input_schema` is `response_model.model_json_schema()`, `tool_choice={"type": "tool", "name": "emit_result"}`, then `response_model.model_validate(tool_use_block.input)`); `tool_loop()` implements the standard Anthropic tool-use loop (call, execute any `tool_use` blocks via `tool_executor`, append `tool_result` blocks, repeat until `stop_reason != "tool_use"` or `max_steps` reached). No network call happens at import time; the client is constructed lazily in `__init__` from `settings.anthropic_api_key`.
- Produces: `app.llm.ollama_provider.OllamaProvider(LLMProvider)` — uses `httpx.AsyncClient` against `settings.ollama_base_url` (`/api/chat` for `chat()`; `structured()` appends a JSON-schema instruction to the system prompt and calls `/api/chat` with `format="json"`, then `response_model.model_validate_json(...)`; `tool_loop()` may raise `NotImplementedError` if Ollama tool support is unavailable for the configured model — this is acceptable for Phase 0, callers must not rely on Ollama for the assistant's tool loop).
- Produces: `app.llm.embeddings.EmbeddingProvider` (ABC, `async def embed(self, texts: list[str]) -> list[list[float]]`), `OllamaEmbeddingProvider(EmbeddingProvider)` (POSTs to `/api/embeddings` per text against `settings.ollama_base_url`/`settings.embedding_model`), `FakeEmbeddingProvider(EmbeddingProvider)` (returns a deterministic pseudo-embedding per text: seed a `random.Random(hash(text))` and produce `settings.embedding_dim` floats in `[-1, 1]`, so identical text always yields identical vectors and tests can assert on similarity without a real model).
- Produces: `app.llm.factory.get_llm_provider() -> LLMProvider` and `app.llm.factory.get_embedding_provider() -> EmbeddingProvider`, both reading `settings.llm_provider` (`"fake" | "anthropic" | "ollama"`) and `settings.embedding_provider` (`"fake" | "ollama"`) respectively, raising `ValueError` on an unrecognized value.

- [ ] **Step 1: Write `backend/app/llm/base.py`**

```python
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, TypedDict, TypeVar

from pydantic import BaseModel

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCallRecord:
    name: str
    input: dict
    output: str


@dataclass
class ChatResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


ToolExecutor = Callable[[str, dict], Awaitable[str]]


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult: ...

    @abstractmethod
    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT: ...

    @abstractmethod
    async def tool_loop(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec],
        tool_executor: ToolExecutor,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 8,
    ) -> ChatResult: ...
```

- [ ] **Step 2: Write `backend/app/llm/fake_provider.py`**

```python
from typing import Any

from pydantic import BaseModel

from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolExecutor,
    ToolSpec,
)


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(
        self,
        responses: list[str] | None = None,
        structured_responses: list[BaseModel | dict] | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._structured_responses = list(structured_responses or [])
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def _next_text(self, messages: list[ChatMessage]) -> str:
        if self._responses:
            return self._responses[self.call_count % len(self._responses)]
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"FAKE: {last_user}"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        self.calls.append({"method": "chat", "messages": messages, "system": system})
        text = self._next_text(messages)
        self.call_count += 1
        return ChatResult(text=text, tokens_in=0, tokens_out=0, model=model or "fake-model")

    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT:
        self.calls.append({"method": "structured", "messages": messages, "system": system})
        if not self._structured_responses:
            raise ValueError("FakeProvider has no scripted structured_responses left")
        idx = self.call_count % len(self._structured_responses)
        raw = self._structured_responses[idx]
        self.call_count += 1
        if isinstance(raw, response_model):
            return raw
        return response_model.model_validate(raw)

    async def tool_loop(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec],
        tool_executor: ToolExecutor,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 8,
    ) -> ChatResult:
        self.calls.append({"method": "tool_loop", "messages": messages, "system": system})
        text = self._next_text(messages)
        self.call_count += 1
        return ChatResult(text=text, tokens_in=0, tokens_out=0, model=model or "fake-model")
```

- [ ] **Step 3: Write the test `backend/tests/llm/__init__.py`** (empty file) and `backend/tests/llm/test_fake_provider.py`

```python
import pytest
from pydantic import BaseModel

from app.llm.fake_provider import FakeProvider


class Verdict(BaseModel):
    passed: bool
    reason: str


@pytest.mark.asyncio
async def test_chat_cycles_through_scripted_responses() -> None:
    provider = FakeProvider(responses=["first", "second"])
    r1 = await provider.chat([{"role": "user", "content": "hi"}])
    r2 = await provider.chat([{"role": "user", "content": "hi"}])
    r3 = await provider.chat([{"role": "user", "content": "hi"}])
    assert [r1.text, r2.text, r3.text] == ["first", "second", "first"]
    assert provider.call_count == 3


@pytest.mark.asyncio
async def test_chat_without_script_echoes_last_user_message() -> None:
    provider = FakeProvider()
    result = await provider.chat([{"role": "user", "content": "hello there"}])
    assert result.text == "FAKE: hello there"


@pytest.mark.asyncio
async def test_structured_validates_into_response_model() -> None:
    provider = FakeProvider(structured_responses=[{"passed": True, "reason": "looks good"}])
    verdict = await provider.structured([{"role": "user", "content": "check"}], response_model=Verdict)
    assert verdict.passed is True
    assert verdict.reason == "looks good"
```

- [ ] **Step 4: Add `pytest-asyncio` config so async tests run, and run the tests**

Add to `backend/pyproject.toml` under a new `[tool.pytest.ini_options]` table:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Run: `cd backend && uv run pytest tests/llm/test_fake_provider.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write `backend/app/llm/embeddings.py`**

```python
import random
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            rng = random.Random(hash(text) & 0xFFFFFFFF)
            vectors.append([rng.uniform(-1, 1) for _ in range(settings.embedding_dim)])
        return vectors


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(base_url=self._base_url, timeout=60.0) as client:
            for text in texts:
                response = await client.post(
                    "/api/embeddings", json={"model": self._model, "prompt": text}
                )
                response.raise_for_status()
                vectors.append(response.json()["embedding"])
        return vectors
```

- [ ] **Step 6: Write `backend/app/llm/ollama_provider.py`**

```python
import json

import httpx

from app.core.config import settings
from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolExecutor,
    ToolSpec,
)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url
        self._default_model = settings.ollama_model

    async def _call(self, messages: list[dict], model: str, extra: dict | None = None) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=120.0) as client:
            payload = {"model": model, "messages": messages, "stream": False, **(extra or {})}
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        full_messages = ([{"role": "system", "content": system}] if system else []) + list(messages)
        data = await self._call(full_messages, model or self._default_model)
        text = data["message"]["content"]
        return ChatResult(text=text, tokens_in=0, tokens_out=0, model=model or self._default_model)

    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT:
        schema = response_model.model_json_schema()
        instruction = (
            f"{system or ''}\n\nRespond with ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema)}"
        )
        full_messages = [{"role": "system", "content": instruction}] + list(messages)
        data = await self._call(
            full_messages, model or self._default_model, extra={"format": "json"}
        )
        return response_model.model_validate_json(data["message"]["content"])

    async def tool_loop(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec],
        tool_executor: ToolExecutor,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 8,
    ) -> ChatResult:
        raise NotImplementedError(
            "OllamaProvider does not support the tool-use loop; use AnthropicProvider or FakeProvider"
        )
```

- [ ] **Step 7: Write `backend/app/llm/anthropic_provider.py`**

```python
import json

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.llm.base import (
    BaseModelT,
    ChatMessage,
    ChatResult,
    LLMProvider,
    ToolCallRecord,
    ToolExecutor,
    ToolSpec,
)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._default_model = settings.anthropic_model

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        response = await self._client.messages.create(
            model=model or self._default_model,
            max_tokens=4096,
            temperature=temperature,
            system=system or "",
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return ChatResult(
            text=text,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            model=response.model,
        )

    async def structured(
        self,
        messages: list[ChatMessage],
        *,
        response_model: type[BaseModelT],
        system: str | None = None,
        model: str | None = None,
    ) -> BaseModelT:
        tool = {
            "name": "emit_result",
            "description": "Emit the structured result.",
            "input_schema": response_model.model_json_schema(),
        }
        response = await self._client.messages.create(
            model=model or self._default_model,
            max_tokens=4096,
            system=system or "",
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit_result"},
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        return response_model.model_validate(tool_use.input)

    async def tool_loop(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec],
        tool_executor: ToolExecutor,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 8,
    ) -> ChatResult:
        anthropic_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        conversation: list[dict] = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        tool_calls: list[ToolCallRecord] = []
        last_response = None

        for _ in range(max_steps):
            last_response = await self._client.messages.create(
                model=model or self._default_model,
                max_tokens=4096,
                system=system or "",
                messages=conversation,
                tools=anthropic_tools,
            )
            conversation.append({"role": "assistant", "content": last_response.content})

            if last_response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in last_response.content:
                if block.type != "tool_use":
                    continue
                output = await tool_executor(block.name, block.input)
                tool_calls.append(ToolCallRecord(name=block.name, input=block.input, output=output))
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": output}
                )
            conversation.append({"role": "user", "content": tool_results})

        assert last_response is not None
        text = "".join(b.text for b in last_response.content if b.type == "text")
        return ChatResult(
            text=text,
            tokens_in=last_response.usage.input_tokens,
            tokens_out=last_response.usage.output_tokens,
            model=last_response.model,
            tool_calls=tool_calls,
        )
```

- [ ] **Step 8: Write `backend/app/llm/factory.py`**

```python
from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingProvider, FakeEmbeddingProvider, OllamaEmbeddingProvider
from app.llm.fake_provider import FakeProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider
    if provider == "fake":
        return FakeProvider()
    if provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider
    if provider == "fake":
        return FakeEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    raise ValueError(f"Unknown embedding provider: {provider!r}")
```

- [ ] **Step 9: Write `backend/app/llm/__init__.py`** (empty file)

- [ ] **Step 10: Write `backend/tests/llm/test_factory.py`**

```python
import pytest

from app.core.config import settings
from app.llm.factory import get_embedding_provider, get_llm_provider
from app.llm.fake_provider import FakeProvider


def test_get_llm_provider_returns_fake_by_default() -> None:
    assert settings.llm_provider == "fake"
    provider = get_llm_provider()
    assert isinstance(provider, FakeProvider)


def test_get_llm_provider_raises_on_unknown() -> None:
    original = settings.llm_provider
    settings.llm_provider = "not-a-real-provider"
    try:
        with pytest.raises(ValueError):
            get_llm_provider()
    finally:
        settings.llm_provider = original


def test_get_embedding_provider_default_is_fake_when_configured() -> None:
    original = settings.embedding_provider
    settings.embedding_provider = "fake"
    try:
        provider = get_embedding_provider()
        assert provider.name == "fake"
    finally:
        settings.embedding_provider = original
```

- [ ] **Step 11: Run all LLM tests**

Run: `cd backend && uv run pytest tests/llm -v`
Expected: PASS (6 passed)

- [ ] **Step 12: Run a manual (not automated) embedding smoke check to confirm the FakeEmbeddingProvider is deterministic**

Run: `cd backend && uv run python -c "
import asyncio
from app.llm.embeddings import FakeEmbeddingProvider

async def main():
    p = FakeEmbeddingProvider()
    a = await p.embed(['hello world'])
    b = await p.embed(['hello world'])
    assert a == b, 'fake embeddings must be deterministic per text'
    print('OK', len(a[0]))

asyncio.run(main())
"`
Expected: prints `OK 1024`

- [ ] **Step 13: Commit**

```bash
git add backend/app/llm backend/tests/llm backend/pyproject.toml
git commit -m "feat: add pluggable llm and embedding provider layer with fake/anthropic/ollama backends"
```

---

## Task 5: Auth (JWT, RBAC) & Seeded Users

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/services/__init__.py`, `backend/app/services/users.py`
- Create: `backend/scripts/__init__.py`, `backend/scripts/seed.py`
- Modify: `backend/app/main.py` (register the auth router)
- Create: `backend/tests/api/__init__.py`, `backend/tests/api/test_auth.py`
- Create: `backend/tests/core/__init__.py`, `backend/tests/core/test_security.py`

**Interfaces:**
- Consumes: `app.db.session.get_session` (T0.2), `app.db.models.User` (T0.2), `app.schemas.auth.LoginRequest/TokenResponse/CurrentUser` (T0.3), `app.core.config.settings` (T0.2).
- Produces: `app.core.security.hash_password(password: str) -> str`, `verify_password(password: str, password_hash: str) -> bool` (both via `bcrypt` directly — `bcrypt.hashpw`/`bcrypt.checkpw`), `create_access_token(user_id: uuid.UUID, role: str) -> str` (JWT with claims `sub` (str(user_id)), `role`, `exp`), `decode_access_token(token: str) -> dict` (raises `jose.JWTError` on invalid/expired).
- Produces: `app.services.users.authenticate(session: Session, email: str, password: str) -> User | None` and `get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None`.
- Produces: `app.api.deps.get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> CurrentUser` (raises `HTTPException(401)` on invalid token or missing user) and `require_role(*roles: Role) -> Callable` — a dependency factory: `require_role("manager")` returns a callable FastAPI dependency that calls `get_current_user` and raises `HTTPException(403)` if `current_user.role not in roles`.
- Produces: `POST /api/auth/login` (body `LoginRequest`, returns `TokenResponse` or 401 on bad credentials) and `GET /api/auth/me` (bearer-auth required, returns `CurrentUser`).
- Produces: `backend/scripts/seed.py` runnable as `uv run python -m scripts.seed`, idempotent (upserts by email), creating `manager@demo.local` (role `manager`) and `analyst@demo.local` (role `analyst`), both password `demo1234`.

- [ ] **Step 1: Write `backend/app/core/security.py`**

```python
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

__all__ = ["hash_password", "verify_password", "create_access_token", "decode_access_token", "JWTError"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_access_token_ttl_hours)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
```

- [ ] **Step 2: Write the test `backend/tests/core/__init__.py`** (empty file) and `backend/tests/core/test_security.py`

```python
import uuid

import pytest

from app.core.security import (
    JWTError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_roundtrip() -> None:
    hashed = hash_password("demo1234")
    assert hashed != "demo1234"
    assert verify_password("demo1234", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_create_and_decode_access_token() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "manager")
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "manager"


def test_decode_invalid_token_raises() -> None:
    with pytest.raises(JWTError):
        decode_access_token("not-a-valid-token")
```

- [ ] **Step 3: Run the security tests**

Run: `cd backend && uv run pytest tests/core/test_security.py -v`
Expected: PASS (3 passed)

- [ ] **Step 4: Write `backend/app/services/__init__.py`** (empty file) and `backend/app/services/users.py`

```python
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.models import User


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)
```

- [ ] **Step 5: Write `backend/app/api/deps.py`**

```python
import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.enums import Role
from app.services.users import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> CurrentUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise credentials_error from exc

    user = get_user_by_id(session, user_id)
    if user is None:
        raise credentials_error
    return CurrentUser.model_validate(user)


def require_role(*roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {roles}, got {current_user.role!r}",
            )
        return current_user

    return _dependency
```

- [ ] **Step 6: Write `backend/app/api/routes/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_session
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.services.users import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = authenticate(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, role=user.role, name=user.name)


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
```

- [ ] **Step 7: Register the auth router in `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.api.routes import auth, health

app = FastAPI(title="Agentic WhatsApp Intelligence & Management Dashboard")

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
```

- [ ] **Step 8: Write `backend/scripts/__init__.py`** (empty file) and `backend/scripts/seed.py`

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import User
from app.db.session import SessionLocal

DEMO_USERS = [
    {"email": "manager@demo.local", "name": "Demo Manager", "role": "manager"},
    {"email": "analyst@demo.local", "name": "Demo Analyst", "role": "analyst"},
]
DEMO_PASSWORD = "demo1234"


def seed_users(session: Session) -> None:
    for spec in DEMO_USERS:
        existing = session.scalar(select(User).where(User.email == spec["email"]))
        if existing is not None:
            continue
        session.add(
            User(
                email=spec["email"],
                name=spec["name"],
                role=spec["role"],
                password_hash=hash_password(DEMO_PASSWORD),
            )
        )
    session.commit()


def main() -> None:
    with SessionLocal() as session:
        seed_users(session)
    print("Seeded demo users: manager@demo.local / analyst@demo.local (password: demo1234)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Write `backend/tests/api/__init__.py`** (empty file) and `backend/tests/api/test_auth.py`

```python
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def test_user(db_session: Session):
    email = f"auth-test-{uuid.uuid4()}@example.com"
    user = User(
        email=email,
        name="Auth Test User",
        role="analyst",
        password_hash=hash_password("correct-password"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.execute(delete(User).where(User.id == user.id))
    db_session.commit()


def test_login_succeeds_with_correct_credentials(client: TestClient, test_user: User) -> None:
    response = client.post(
        "/api/auth/login", json={"email": test_user.email, "password": "correct-password"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "analyst"
    assert body["access_token"]


def test_login_rejects_wrong_password(client: TestClient, test_user: User) -> None:
    response = client.post(
        "/api/auth/login", json={"email": test_user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client: TestClient, test_user: User) -> None:
    login_response = client.post(
        "/api/auth/login", json={"email": test_user.email, "password": "correct-password"}
    )
    token = login_response.json()["access_token"]
    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_user.email
    assert me_response.json()["role"] == "analyst"
```

- [ ] **Step 10: Run the auth tests**

Run: `cd backend && uv run pytest tests/api/test_auth.py tests/core/test_security.py -v`
Expected: PASS (7 passed)

- [ ] **Step 11: Run the seed script against the running database and verify idempotency**

Run: `cd backend && uv run python -m scripts.seed`
Expected: prints the seed confirmation message.
Run: `cd backend && uv run python -m scripts.seed` (again)
Expected: prints the same message, and `select count(*) from users` is still 2 (no duplicates) — verify with:
`uv run python -c "from sqlalchemy import create_engine, text; from app.core.config import settings; print(create_engine(settings.database_url).connect().execute(text('select count(*) from users')).scalar())"`
Expected: `2`

- [ ] **Step 12: Run the full backend test suite and lint/type-check**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass (health, db, schemas, llm, core, api — should total in the low 20s).
Run: `cd backend && uv run ruff check app`
Expected: no errors.
Run: `cd backend && uv run mypy app`
Expected: no errors (fix any typing issues found before proceeding).

- [ ] **Step 13: Commit**

```bash
git add backend/app/core/security.py backend/app/api backend/app/services backend/scripts backend/app/main.py backend/tests/api backend/tests/core
git commit -m "feat: add jwt auth, rbac dependency, login/me endpoints, seed script"
```

---

## Self-Review Notes (for the plan author, already applied above)

- **Spec coverage:** Docker stack (§4, PLAN.md), DB model (§8), Pydantic contracts (§8 fields mirrored), LLM/embedding pluggability (§2, §6), JWT+RBAC (§2 Auth decision) are each covered by a task above.
- **Type consistency:** `role` is the literal string `"manager"`/`"analyst"` in the ORM column (T0.2), the `Role` Pydantic type (T0.3), the JWT claim and `require_role` (T0.5) — verified consistent throughout.
- **No placeholders:** every step above contains complete, runnable code or an exact shell command with an expected result.
- **Scope:** this plan stops at the foundation contracts; ingestion, agents, memory, dashboard pages are out of scope and will be separate plans (Phase 1–4) that consume these contracts.
