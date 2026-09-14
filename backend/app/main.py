from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(title="Agentic WhatsApp Intelligence & Management Dashboard")

app.include_router(health.router, prefix="/api")
