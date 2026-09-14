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
