def test_health(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
