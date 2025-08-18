import os, json, hmac, hashlib, pytest
from httpx import AsyncClient
from src.main import app

def sig(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

def inbound(pnid: str, msg_id: str):
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": pnid},
                    "messages": [{"id": msg_id, "from": "+12025550123", "type": "text", "timestamp": "1"}],
                    "statuses": [{"id": msg_id, "status": "delivered", "timestamp": "2"}],
                }
            }]
        }]
    }

@pytest.mark.asyncio
async def test_inbound_happy(monkeypatch):
    # Use SQLite for integration tests if desired
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "dev-app-secret")
    headers = {"Authorization": "Bearer 00000000-0000-0000-0000-000000000000"}
    async with AsyncClient(app=app, base_url="http://test", headers=headers) as ac:
        # Onboard channel
        r = await ac.post("/api/v1/wa/channel", json={
            "phone_number_id": "PNID1", "business_phone": "+911234567890",
            "access_token": "tkn", "verify_token": "vtkn", "webhook_url": "https://example.com"
        })
        assert r.status_code == 200

    body = json.dumps(inbound("PNID1", "MSG1")).encode()
    s = sig("dev-app-secret", body)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r1 = await ac.post("/api/v1/wa/webhook", content=body, headers={"X-Hub-Signature-256": s})
        assert r1.status_code == 200
        r2 = await ac.post("/api/v1/wa/webhook", content=body, headers={"X-Hub-Signature-256": s})
        assert r2.status_code == 200
