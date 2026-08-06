"""
限流模块：令牌桶算法，用Redis Lua脚本保证"读取-计算-写入"的原子性

为什么不用简单的Python逻辑 + 多次Redis调用：
    多个请求(可能落在不同实例上)会产生竞态条件——
    两个请求都读到"桶里还有1个令牌"，各自计算、各自写回，
    后写的会覆盖先写的，导致令牌被"超发"。
    Lua脚本能保证这段逻辑在Redis内部一次性、不被打断地执行完。
"""

import time

from app.cache import redis_client

# Lua脚本：令牌桶核心逻辑
# KEYS[1]  = 这个限流桶在Redis里的key
# ARGV[1]  = 桶的容量(capacity)
# ARGV[2]  = 令牌生成速率(每秒生成多少个)
# ARGV[3]  = 当前时间戳(毫秒)
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- 读取桶里现有的令牌数和上次更新时间，如果是第一次访问(key不存在)，
-- 就当作"桶是满的、上次更新时间就是现在"
local bucket = redis.call("HMGET", key, "tokens", "last_refill_time")
local tokens = tonumber(bucket[1])
local last_refill_time = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill_time = now
end

-- 计算这段时间新生成的令牌数，累加后不能超过桶容量
local elapsed = math.max(0, now - last_refill_time)
local new_tokens = elapsed * refill_rate / 1000.0
tokens = math.min(capacity, tokens + new_tokens)

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

-- 把最新的令牌数和时间戳写回去，设置一个过期时间(避免长期不用的key一直占内存)
redis.call("HMSET", key, "tokens", tokens, "last_refill_time", now)
redis.call("EXPIRE", key, 3600)

return allowed
"""


async def is_allowed(bucket_key: str, capacity: int, refill_rate: float) -> bool:
    """
    检查是否允许通过限流。

    bucket_key: 限流桶的唯一标识，比如按IP限流就用 "ratelimit:1.2.3.4"
    capacity: 桶的容量(最多能攒多少令牌，即能容忍的突发上限)
    refill_rate: 每秒生成多少个令牌(长期平均速率)
    """
    now_ms = int(time.time() * 1000)
    result = await redis_client.eval(
        TOKEN_BUCKET_LUA, 1, bucket_key, capacity, refill_rate, now_ms
    )
    return result == 1