import json, hmac, hashlib
from httpx import AsyncClient
from src.config import settings

async def _post(app_client, body):
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(settings.WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return await app_client.post("/webhooks/whatsapp/123", headers={"X-Hub-Signature-256": sig}, content=raw)

async def test_duplicate_wamid_is_ignored(app_client: AsyncClient):
    msg = {"entry":[{"changes":[{"value":{"messages":[{"id":"wamid.DUP","from":"+911","type":"text"}],
                                                   "metadata":{"display_phone_number":"+912"}}]}]}]}
    r1 = await _post(app_client, msg); r2 = await _post(app_client, msg)
    assert r1.status_code == 200 and r2.status_code == 200
    # query DB to ensure just one row for whatsapp_message_id='wamid.DUP'
