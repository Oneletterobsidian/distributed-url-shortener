"""
Redis缓存层：封装"短码 -> 长链接"这个映射的缓存读写
"""

import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# 缓存key的前缀，避免跟未来其他功能(比如限流、点击统计)用到的key搞混
CACHE_KEY_PREFIX = "shortlink:"


async def get_cached_long_url(short_code: str) -> str | None:
    """查缓存，命中返回长链接字符串，未命中返回None"""
    return await redis_client.get(CACHE_KEY_PREFIX + short_code)


async def set_cached_long_url(short_code: str, long_url: str) -> None:
    """写入缓存"""
    await redis_client.set(CACHE_KEY_PREFIX + short_code, long_url)