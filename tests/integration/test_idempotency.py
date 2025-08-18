from httpx import AsyncClient

async def test_inbound_idempotency_dedup(app_client: AsyncClient, seed_channel, pg_session):
    wamid = "wamid.duplicate.1"
    payload = {"entry":[{"changes":[{"value":{"messages":[{"id": wamid, "from":"", "to":"", "timestamp":"0"}]}}]}]}
    for _ in range(2):
        r = await app_client.post("/webhooks/whatsapp", json=payload, headers={"X-Hub-Signature-256": "sha256=<valid>"})
        assert r.status_code == 200
    # Expect exactly one row with this wamid (DB unique)
    count = (await pg_session.execute("SELECT count(*) FROM messages WHERE whatsapp_message_id=:id", {"id": wamid})).scalar_one()
    assert count == 1
