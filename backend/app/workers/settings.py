from typing import ClassVar

from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.jobs import process_batch


class WorkerSettings:
    functions: ClassVar = [process_batch]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
