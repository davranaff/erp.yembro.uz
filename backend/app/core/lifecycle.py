from __future__ import annotations

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logger import setup_logger
from app.db.pool import Database
from app.db.redis_client import RedisClient
from app.taskiq_app import broker


async def on_startup(app: FastAPI) -> None:
    settings = get_settings()
    setup_logger(settings.environment, settings.log_level)
    db = Database(
        dsn=settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()
    redis = RedisClient(settings.redis_url)
    await redis.connect()

    app.state.settings = settings
    app.state.db = db
    app.state.redis = redis
    await broker.startup()


async def on_shutdown(app: FastAPI) -> None:
    if hasattr(app.state, "db"):
        await app.state.db.disconnect()
    if hasattr(app.state, "redis"):
        await app.state.redis.disconnect()
    await broker.shutdown()
