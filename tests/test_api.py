import time

from fastapi.testclient import TestClient

from argan_api.main import app

client = TestClient(app)


def test_endpoints_and_job():
    assert client.get("/health").json()["status"] == "ok"
    d = client.get("/config/defaults").json()
    assert {"scenario", "schema"} <= d.keys() and len(d["schema"]) > 30
    assert client.get("/data/summary").json()["fx_last"] > 1e6
    jid = client.post("/simulations", json={"scenario": {"n_paths": 800, "robust": False, "flip_analysis": False}, "mode": "expert"}).json()["id"]
    for _ in range(120):
        j = client.get(f"/simulations/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.5)
    assert j["status"] == "done", j.get("error")
    assert abs(sum(j["result"]["recommended"]["weights"]) - 1) < 1e-9
    assert "<html" in client.get(f"/simulations/{jid}/report").text
    assert client.get("/").status_code == 200 and client.get("/expert").status_code == 200


def test_validation_error():
    r = client.post("/simulations", json={"scenario": {"deposit_rate_pct": 50, "borrow_rate_pct": 10}})
    assert r.status_code == 422
