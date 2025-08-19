import hmac, hashlib, json
from httpx import AsyncClient
from src.config import settings

async def test_whatsapp_get_verify_ok(app_client: AsyncClient):
    r = await app_client.get("/webhooks/whatsapp/123",
        params={"hub.mode":"subscribe","hub.challenge":"42","hub.verify_token":settings.WHATSAPP_VERIFY_TOKEN})
    assert r.status_code == 200
    assert r.json() == 42

async def test_whatsapp_post_signature_ok(app_client: AsyncClient):
    body = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.X",
                                    "from": "+9112345",
                                    "type": "text"
                                }
                            ],
                            "metadata": {
                                "display_phone_number": "+9112345"
                            }
                        }
                    }
                ]
            }
        ]
    }
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(settings.WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    r = await app_client.post("/webhooks/whatsapp/123", headers={"X-Hub-Signature-256": sig}, json=body)
    assert r.status_code == 200

async def test_whatsapp_post_signature_bad(app_client: AsyncClient):
    r = await app_client.post("/webhooks/whatsapp/123", headers={"X-Hub-Signature-256": "sha256=deadbeef"}, json={})
    assert r.status_code == 403
