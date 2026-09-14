from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    actions,
    activity,
    assistant,
    auth,
    chats,
    dashboard,
    escalations,
    health,
    ingest,
    items,
    search,
)
from app.core.config import settings

app = FastAPI(title="Agentic WhatsApp Intelligence & Management Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(actions.router, prefix="/api")
app.include_router(activity.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
for router in (chats.router, dashboard.router, escalations.router, items.router, search.router):
    app.include_router(router, prefix="/api")
