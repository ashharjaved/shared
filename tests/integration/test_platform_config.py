async def test_config_set_get_404(client_tenant):
    # set
    r = await client_tenant.put("/platform/config", json={"key":"whatsapp.verify_token","value":"x"})
    assert r.status_code == 200
    # get
    r = await client_tenant.get("/platform/config/whatsapp.verify_token")
    assert r.status_code == 200 and r.json()["value"] == "x"
    # missing -> 404
    r = await client_tenant.get("/platform/config/not.there")
    assert r.status_code == 404
