def test_app_boots_and_has_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data == b"ok"
