import uuid

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User
from app.main import app
from app.schemas.auth import CurrentUser

# `require_role` (app/api/deps.py) has zero production usages yet, so this
# module registers a throwaway route purely to prove the dependency works
# end-to-end through FastAPI's real dependency-injection chain (bearer
# token -> JWT decode -> DB user lookup -> role check) -- the same chain a
# real Manager-only production route will use in a later phase. It is never
# a production route: it is added to `app` only for the lifetime of the
# `client_with_test_route` fixture and removed immediately after.
TEST_ONLY_PATH = "/api/test-only/manager-check"

_test_router = APIRouter()
_require_manager = require_role("manager")


@_test_router.get("/test-only/manager-check")
def _manager_only_route(current_user: CurrentUser = Depends(_require_manager)) -> dict:
    return {"ok": True, "role": current_user.role}


@pytest.fixture()
def client_with_test_route() -> TestClient:
    app.include_router(_test_router, prefix="/api")
    try:
        yield TestClient(app)
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", None) != TEST_ONLY_PATH
        ]


@pytest.fixture()
def db_session():
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        yield session


def _make_user(db_session: Session, role: str) -> User:
    user = User(
        email=f"rbac-{role}-{uuid.uuid4()}@example.com",
        name=f"RBAC {role.title()}",
        role=role,
        password_hash=hash_password("correct-password"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def manager_user(db_session: Session):
    user = _make_user(db_session, "manager")
    yield user
    db_session.execute(delete(User).where(User.id == user.id))
    db_session.commit()


@pytest.fixture()
def analyst_user(db_session: Session):
    user = _make_user(db_session, "analyst")
    yield user
    db_session.execute(delete(User).where(User.id == user.id))
    db_session.commit()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "correct-password"}
    )
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token


def test_require_role_allows_matching_role(
    client_with_test_route: TestClient, manager_user: User
) -> None:
    token = _login(client_with_test_route, manager_user.email)
    response = client_with_test_route.get(
        TEST_ONLY_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "role": "manager"}


def test_require_role_rejects_non_matching_role(
    client_with_test_route: TestClient, analyst_user: User
) -> None:
    token = _login(client_with_test_route, analyst_user.email)
    response = client_with_test_route.get(
        TEST_ONLY_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_require_role_rejects_missing_token(client_with_test_route: TestClient) -> None:
    response = client_with_test_route.get(TEST_ONLY_PATH)
    assert response.status_code == 401
