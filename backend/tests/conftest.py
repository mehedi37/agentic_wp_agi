import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.checkpoints import setup_checkpoints
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chat
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def checkpoint_schema():
    setup_checkpoints()


@pytest.fixture(autouse=True)
def simulated_outbound(monkeypatch):
    monkeypatch.setattr(settings, "email_mode", "simulated")
    monkeypatch.setattr(settings, "whatsapp_mode", "simulated")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


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
