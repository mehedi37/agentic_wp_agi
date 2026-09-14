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
