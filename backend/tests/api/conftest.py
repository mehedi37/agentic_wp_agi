import uuid

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.session import get_session
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            app.dependency_overrides[get_session] = lambda: session
            try:
                yield session
            finally:
                app.dependency_overrides.pop(get_session, None)
        transaction.rollback()
    engine.dispose()


@pytest.fixture()
def analyst_user(db_session: Session):
    user = User(
        email=f"ingest-analyst-{uuid.uuid4()}@example.com",
        name="Ingest Analyst",
        role="analyst",
        password_hash=hash_password("correct-password"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.execute(delete(User).where(User.id == user.id))
    db_session.commit()


@pytest.fixture()
def analyst_token(analyst_user: User) -> str:
    return create_access_token(analyst_user.id, analyst_user.role)
