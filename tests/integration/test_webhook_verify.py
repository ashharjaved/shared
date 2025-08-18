import os, pytest
from httpx import AsyncClient
from src.main import app
import hmac, hashlib

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

async def test_webhook_get_verify_valid(app_client: AsyncClient):
    r = await app_client.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "tenant-override-or-fallback",
        "hub.challenge": "abc123"
    })
    assert r.status_code == 200
    assert r.text == "abc123"

async def test_webhook_get_verify_invalid(app_client: AsyncClient):
    r = await app_client.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "WRONG",
        "hub.challenge": "abc123"
    })
    assert r.status_code in (401,403)

async def test_webhook_post_signature_valid(app_client: AsyncClient, secret=b"shh"):
    body = b'{"entry":[{"changes":[{"value":{"messages":[{"id":"wamid.1"}]}}]}]}'
    sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    r = await app_client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": sig})
    assert r.status_code == 200

async def test_webhook_post_signature_invalid(app_client: AsyncClient):
    r = await app_client.post("/webhooks/whatsapp", content=b"{}", headers={"X-Hub-Signature-256": "sha256=deadbeef"})
    assert r.status_code in (401,403)
