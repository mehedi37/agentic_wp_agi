import asyncio
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.action import plan_action
from app.agents.checkpoints import setup_checkpoints
from app.agents.monitor import run_monitor
from app.agents.pipeline_graph import run_pipeline_for_chat
from app.core.security import hash_password
from app.db.models import Chat, User
from app.db.session import SessionLocal
from app.llm.factory import get_embedding_provider, get_llm_provider
from app.services.ingestion import ingest_export

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


async def seed_demo() -> None:
    setup_checkpoints()
    with SessionLocal() as session:
        seed_users(session)
        samples = Path(os.environ.get("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data" / "sample")))
        exports = samples / "exports"
        if not exports.is_dir():
            raise FileNotFoundError(f"Sample exports missing: {exports}")
        llm, embedder = get_llm_provider(), get_embedding_provider()
        for path in sorted(exports.iterdir()):
            if path.suffix not in (".txt", ".zip"):
                continue
            name = path.stem.replace("_", " ").title()
            chat = session.scalar(select(Chat).where(Chat.name == name, Chat.source == "export"))
            if chat is None:
                chat = Chat(name=name, source="export", type="group", timezone="Asia/Dhaka")
                session.add(chat)
                session.flush()
            await ingest_export(session, chat_id=chat.id, filename=path.name, file_bytes=path.read_bytes())
            await run_pipeline_for_chat(session, chat_id=chat.id, analyst_llm=llm,
                                        judge_llm=llm, embedder=embedder)
            for escalation in run_monitor(session, chat_id=chat.id):
                await plan_action(session, escalation, llm)
            session.commit()
            print(f"Processed {name}")
    print("Seeded demo users: manager@demo.local / analyst@demo.local (password: demo1234)")


if __name__ == "__main__":
    asyncio.run(seed_demo())
