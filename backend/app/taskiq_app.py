from __future__ import annotations

from taskiq_redis import RedisAsyncResultBackend

try:
    from taskiq_redis import RedisStreamBroker as RedisBroker
except ImportError:  # pragma: no cover - compatibility with newer taskiq-redis
    from taskiq_redis import ListQueueBroker as RedisBroker

from app.core.config import get_settings


settings = get_settings()

broker = RedisBroker(url=settings.redis_url)
broker = broker.with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis_url)
)
