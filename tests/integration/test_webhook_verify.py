import os, pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_verify_token_ok(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "dev-verify-token")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/v1/wa/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "dev-verify-token",
            "hub.challenge": "1234",
        })
        assert r.status_code == 200
        assert r.text == "1234"

@pytest.mark.asyncio
async def test_verify_token_bad():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/v1/wa/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "nope",
            "hub.challenge": "1234",
        })
        assert r.status_code == 403
