from __future__ import annotations

from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from app.core.config import get_settings


settings = get_settings()

broker = RedisStreamBroker(url=settings.redis_url)
broker = broker.with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis_url)
)
