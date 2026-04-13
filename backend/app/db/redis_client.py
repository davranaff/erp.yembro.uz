from __future__ import annotations

import inspect

from redis.asyncio import Redis


class RedisClient:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Redis | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = Redis.from_url(self._url)
        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client is None:
            return

        maybe_result = self._client.close()
        if inspect.isawaitable(maybe_result):
            await maybe_result

        if self._client.connection_pool is not None:
            maybe_pool_result = self._client.connection_pool.disconnect(inuse_connections=True)
            if inspect.isawaitable(maybe_pool_result):
                await maybe_pool_result
        self._client = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("RedisClient is not connected")
        return self._client
