from typing import ClassVar
from zoneinfo import ZoneInfo

from arq import cron
from arq.connections import RedisSettings

from app.agents.checkpoints import setup_checkpoints
from app.core.config import settings
from app.workers.jobs import consolidate, monitor_all, process_batch


async def startup(ctx: dict) -> None:
    setup_checkpoints()


class WorkerSettings:
    on_startup = startup
    functions: ClassVar = [process_batch, monitor_all, consolidate]
    cron_jobs: ClassVar = [cron(monitor_all, minute={0, 15, 30, 45}),
                          cron(consolidate, hour=2, minute=0)]
    timezone = ZoneInfo(settings.app_timezone)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
