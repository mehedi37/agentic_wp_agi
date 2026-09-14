from fastapi import FastAPI

from app.api.routes import auth, health

app = FastAPI(title="Agentic WhatsApp Intelligence & Management Dashboard")

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
