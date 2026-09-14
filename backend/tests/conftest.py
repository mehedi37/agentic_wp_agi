import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models import Chat
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.rollback()
    session.close()


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
