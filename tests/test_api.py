"""
测试完整的API接口——数据库和Redis都已经被替换成测试专用的假版本
"""

import pytest


@pytest.mark.asyncio
async def test_create_short_link_returns_short_code(client):
    response = await client.post(
        "/links", json={"long_url": "https://www.anthropic.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "short_code" in data
    assert data["long_url"] == "https://www.anthropic.com"


@pytest.mark.asyncio
async def test_redirect_to_nonexistent_short_code_returns_404(client):
    response = await client.get("/nonexistent-code", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_redirect_follows_to_long_url(client):
    create_response = await client.post(
        "/links", json={"long_url": "https://www.anthropic.com"}
    )
    short_code = create_response.json()["short_code"]

    redirect_response = await client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == "https://www.anthropic.com"