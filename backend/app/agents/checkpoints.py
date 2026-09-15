from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.orm import Session

from app.core.config import settings


@lru_cache(maxsize=1)
def setup_checkpoints() -> None:
    with PostgresSaver.from_conn_string(settings.database_url.replace("postgresql+psycopg://", "postgresql://")) as saver:
        # Serialize first-start schema migrations across API and worker processes.
        saver.conn.execute("SELECT pg_advisory_lock(731205)")  # type: ignore[union-attr]
        try:
            saver.setup()
        finally:
            saver.conn.execute("SELECT pg_advisory_unlock(731205)")  # type: ignore[union-attr]


def session_checkpointer(session: Session) -> PostgresSaver:
    raw_connection = session.connection().connection.driver_connection
    assert raw_connection is not None
    saver = PostgresSaver(raw_connection)
    # Use ordinary cursors/savepoints on the application's existing transaction.
    saver.supports_pipeline = False
    return saver
