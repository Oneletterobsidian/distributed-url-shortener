"""
测试限流模块——用fakeredis代替真实Redis，验证令牌桶逻辑本身对不对
"""

import pytest

import app.rate_limiter as rate_limiter_module


@pytest.mark.asyncio
async def test_allows_requests_within_capacity(fake_redis, monkeypatch):
    """在桶容量范围内的请求，应该都被允许"""
    # 猴子补丁：把rate_limiter模块里的redis_client，临时换成fake_redis
    monkeypatch.setattr(rate_limiter_module, "redis_client", fake_redis)

    for _ in range(5):  # capacity=5
        allowed = await rate_limiter_module.is_allowed(
            "test-bucket", capacity=5, refill_rate=1
        )
        assert allowed is True


@pytest.mark.asyncio
async def test_rejects_requests_beyond_capacity(fake_redis, monkeypatch):
    """超过桶容量的突发请求，应该被拒绝"""
    monkeypatch.setattr(rate_limiter_module, "redis_client", fake_redis)

    # 先把5个令牌全部用完
    for _ in range(5):
        await rate_limiter_module.is_allowed("test-bucket-2", capacity=5, refill_rate=1)

    # 第6个请求，紧接着发生(几乎没有时间间隔，令牌来不及回血)
    allowed = await rate_limiter_module.is_allowed(
        "test-bucket-2", capacity=5, refill_rate=1
    )
    assert allowed is False