"""
pytest公共fixture配置
"""

import pytest
import pytest_asyncio
import fakeredis.aioredis
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def fake_redis():
    """提供一个内存模拟的Redis客户端，代替真实Redis连接"""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest_asyncio.fixture
async def test_db_session():
    """
    提供一个内存SQLite数据库，代替真实Postgres。
    每个测试用例都是全新的、干净的一份，互不干扰。
    """
    # sqlite+aiosqlite:///:memory: 表示"内存里的临时SQLite数据库"，
    # 不落盘、进程结束就消失，非常适合测试场景
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    async with TestSessionLocal() as session:
        yield session

    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(test_db_session, fake_redis, monkeypatch):
    """
    提供一个能直接调用FastAPI接口的测试客户端，
    背后所有外部依赖(数据库、Redis)都已经替换成测试专用的假版本。
    """
    # 依赖覆盖：把接口里 Depends(get_db) 这部分，换成指向测试数据库的session
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    # 猴子补丁：把cache.py和rate_limiter.py里真实的redis_client都换成fake_redis
    import app.cache as cache_module
    import app.rate_limiter as rate_limiter_module
    import app.analytics as analytics_module

    monkeypatch.setattr(cache_module, "redis_client", fake_redis)
    monkeypatch.setattr(rate_limiter_module, "redis_client", fake_redis)
    monkeypatch.setattr(analytics_module, "redis_client", fake_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()