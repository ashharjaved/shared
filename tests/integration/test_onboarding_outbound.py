import os, pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_onboard_and_outbound_preview(monkeypatch):
    headers = {"Authorization": "Bearer 00000000-0000-0000-0000-000000000000"}
    async with AsyncClient(app=app, base_url="http://test", headers=headers) as ac:
        r = await ac.post("/api/v1/wa/channel", json={
            "phone_number_id": "PNID2", "business_phone": "+911234567891",
            "access_token": "tkn2", "verify_token": "vtkn2", "webhook_url": "https://example.com/wh"
        })
        assert r.status_code == 200
        r2 = await ac.post("/api/v1/wa/messages", json={"to": "+12025550123", "text": "hello"})
        assert r2.status_code == 200
        data = r2.json()["data"]
        assert "/PNID2/messages" in data["endpoint"]
        assert data["payload"]["to"] == "+12025550123"
