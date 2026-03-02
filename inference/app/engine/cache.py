import json

import redis.asyncio as aioredis


class ResponseCache:
    def __init__(self, redis_url: str = "redis://redis:6379/3"):
        self.redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def connect(self):
        self._redis = aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )

    async def close(self):
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> dict | None:
        if not self._redis:
            return None
        data = await self._redis.get(f"cache:{key}")
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: dict, ttl: int = 3600) -> None:
        if not self._redis:
            return
        await self._redis.setex(f"cache:{key}", ttl, json.dumps(value))

    async def invalidate(self, key: str) -> None:
        if not self._redis:
            return
        await self._redis.delete(f"cache:{key}")
