"""
点击分析：用 Redis HyperLogLog 统计短链接的独立访客数(去重点击量)
"""

from app.cache import redis_client

HLL_KEY_PREFIX = "hll:"


async def record_click(short_code: str, visitor_id: str) -> None:
    """记录一次点击，visitor_id用来判断是否为同一人(比如客户端IP)"""
    await redis_client.pfadd(HLL_KEY_PREFIX + short_code, visitor_id)


async def get_unique_visitor_count(short_code: str) -> int:
    """获取某个短链接的独立访客数估算值"""
    return await redis_client.pfcount(HLL_KEY_PREFIX + short_code)