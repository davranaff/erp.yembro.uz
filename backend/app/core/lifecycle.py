from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logger import setup_logger
from app.db.pool import Database
from app.db.redis_client import RedisClient
from app.taskiq_app import broker

logger = logging.getLogger(__name__)


async def _register_telegram_webhook(settings, db) -> None:
    bot_token = str(settings.telegram_bot_token or "").strip()
    webhook_secret = str(settings.telegram_webhook_secret or "").strip()
    public_api_url = str(settings.public_api_base_url or "").strip()
    if not (bot_token and webhook_secret and public_api_url):
        logger.info(
            "Telegram webhook auto-registration skipped "
            "(token=%s, secret=%s, api_url=%s)",
            "set" if bot_token else "missing",
            "set" if webhook_secret else "missing",
            "set" if public_api_url else "missing",
        )
        return
    try:
        from app.services.telegram_bot import TelegramBotService

        service = TelegramBotService(db)
        result = await service.register_webhook()
        if result.get("ok"):
            logger.info("Telegram webhook active: %s", result.get("webhook_url"))
        else:
            logger.warning("Telegram webhook registration failed: %s", result.get("description"))
    except Exception:
        logger.exception("Telegram webhook auto-registration error")


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
    await _register_telegram_webhook(settings, db)


async def on_shutdown(app: FastAPI) -> None:
    if hasattr(app.state, "db"):
        await app.state.db.disconnect()
    if hasattr(app.state, "redis"):
        await app.state.redis.disconnect()
    await broker.shutdown()
