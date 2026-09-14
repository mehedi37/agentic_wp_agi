import uuid

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_process_batch(chat_id: uuid.UUID) -> None:
    """Enqueues the `"process_batch"` ARQ job by name. The job function
    itself is registered later (Task 5's `app.workers.settings.WorkerSettings`)
    -- enqueueing by string name means this module never imports Task 5's
    code, so Task 1 has no forward dependency on it."""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("process_batch", str(chat_id))
    finally:
        await pool.close()
