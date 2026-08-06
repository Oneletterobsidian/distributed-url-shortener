"""
分布式短链接服务 - 入口文件
第1步：环境搭建 ✅
第2步：数据模型设计 ✅
第3步：短码生成算法 ✅
"""
from app.cache import get_cached_long_url, set_cached_long_url

import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, engine, get_db
from app import models  # noqa: F401  确保models注册进Base.metadata
from app.snowflake import SnowflakeGenerator, base62_encode
from sqlalchemy.exc import IntegrityError

from fastapi import Request
from app.rate_limiter import is_allowed

from app.analytics import record_click, get_unique_visitor_count

RATE_LIMIT_CAPACITY = 5       # 桶容量：最多允许5个突发请求
RATE_LIMIT_REFILL_RATE = 1    # 每秒生成1个令牌(长期平均限速:1次/秒)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INSTANCE_ID = os.getenv("INSTANCE_ID", "unknown")

# 把INSTANCE_ID(字符串"1"/"2"/"3")转成整数当作雪花算法的机器ID
# 如果不是纯数字(比如本地不通过docker-compose直接跑的情况)，兜底用0
MACHINE_ID = int(INSTANCE_ID) if INSTANCE_ID.isdigit() else 0

# 每个实例只需要一个生成器，整个进程生命周期内复用同一个
snowflake_generator = SnowflakeGenerator(machine_id=MACHINE_ID)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except IntegrityError:
            # 多个实例同时尝试建表时，只有一个能成功，
            # 其他实例会撞上"表已存在"的竞态错误，这里直接忽略
            pass
    yield

app = FastAPI(title="Distributed URL Shortener", version="0.3.0", lifespan=lifespan)

class CreateLinkRequest(BaseModel):
    long_url: str


@app.get("/health")
async def health_check():
    status = {"instance": INSTANCE_ID, "api": "ok", "postgres": "unknown", "redis": "unknown"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = f"error: {e}"

    try:
        r = redis.from_url(REDIS_URL)
        await r.ping()
        status["redis"] = "ok"
        await r.aclose()
    except Exception as e:
        status["redis"] = f"error: {e}"

    return status


@app.get("/")
async def root():
    return {"message": "Distributed URL Shortener - Step 3 完成", "instance": INSTANCE_ID}


@app.post("/links")
async def create_short_link(
    payload: CreateLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """创建一个新的短链接"""
    client_ip = request.client.host
    bucket_key = f"ratelimit:{client_ip}"

    allowed = await is_allowed(
        bucket_key, RATE_LIMIT_CAPACITY, RATE_LIMIT_REFILL_RATE
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    snowflake_id = snowflake_generator.next_id()
    short_code = base62_encode(snowflake_id)

    link = models.ShortLink(
        short_code=short_code,
        long_url=payload.long_url,
        created_by_instance=INSTANCE_ID,
    )
    db.add(link)
    await db.commit()

    await set_cached_long_url(short_code, payload.long_url)

    return {
        "short_code": short_code,
        "long_url": payload.long_url,
        "created_by_instance": INSTANCE_ID,
    }

@app.get("/links/{short_code}/stats")
async def get_link_stats(short_code: str):
    """查询某个短链接的独立访客数(估算值)"""
    unique_visitors = await get_unique_visitor_count(short_code)
    return {"short_code": short_code, "unique_visitors": unique_visitors}

# 注意：这个路由必须放在文件最后，因为它会匹配"任何路径"，
# 如果放在/health、/之前，会抢先把这些请求当成short_code处理
@app.get("/{short_code}")
async def redirect_to_long_url(
    short_code: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """访问短链接，自动跳转到对应的长链接"""

    # 先查缓存
    cached_url = await get_cached_long_url(short_code)
    if cached_url is not None:
        await record_click(short_code, request.client.host)
        return RedirectResponse(url=cached_url)

    # 缓存未命中，查数据库
    result = await db.execute(
        select(models.ShortLink).where(models.ShortLink.short_code == short_code)
    )
    link = result.scalar_one_or_none()

    if link is None:
        raise HTTPException(status_code=404, detail="短链接不存在")

    await set_cached_long_url(short_code, link.long_url)
    await record_click(short_code, request.client.host)

    return RedirectResponse(url=link.long_url)