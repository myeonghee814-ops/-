import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_token_endpoint_returns_not_implemented() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/token", data={"username": "someone@example.com", "password": "hunter2"}
        )

    assert response.status_code == 501


@pytest.mark.asyncio
async def test_token_endpoint_appears_in_openapi_schema() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert "/api/v1/auth/token" in response.json()["paths"]
