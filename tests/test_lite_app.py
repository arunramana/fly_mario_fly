"""The lite HTTP API end to end with a fake engine: no emulator and no MaleCNS data needed."""
import threading
import time

import pytest
from fastapi.testclient import TestClient
from lite_support import FakeEngine, config, request

from fly_mario_fly.lite.app import create_lite_app


def body(**kw):
    return request(**kw).model_dump(mode="json")


@pytest.fixture
def client(tmp_path):
    cfg = config(tmp_path)
    eng = FakeEngine()
    with TestClient(create_lite_app(cfg, engine=eng)) as c:
        c.engine, c.cfg = eng, cfg
        yield c


def finish(client, run_id, t=5):
    end = time.time() + t
    while time.time() < end:
        r = client.get(f"/runs/{run_id}").json()
        if r["status"] in ("done", "failed"):
            return r
        time.sleep(0.01)
    raise AssertionError("never finished")


def test_health(client):
    h = client.get("/health").json()
    assert h["ok"] and h["queue"] == 0 and h["version"].endswith("testbundle")


def test_the_page_can_load_its_static_files(client):
    assert client.get("/registry").json()["presets"] == ["blank"]
    assert [lv["id"] for lv in client.get("/levels").json()] == ["1-1", "1-2"]
    assert client.get("/flies/blank").json()["name"] == "blank"
    assert client.get("/levels/1-1/thumbnail.png").status_code == 200
    assert client.get("/objects/goomba/icon.png").headers["content-type"] == "image/png"
    assert client.get("/flies/champion_e1s").status_code == 404
    assert client.get("/objects/nothing/icon.png").status_code == 404


def test_run_poll_video(client):
    r = client.post("/runs", json=body())
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    done = finish(client, run_id)
    assert done["status"] == "done" and done["video_url"] == f"/videos/{run_id}.mp4"
    v = client.get(done["video_url"])
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    assert "immutable" in v.headers["cache-control"] and "max-age=31536000" in v.headers["cache-control"]
    assert v.content[4:8] == b"ftyp"
    assert client.get(done["video_url"], headers={"Range": "bytes=0-9"}).status_code == 206
    again = client.post("/runs", json=body()).json()
    assert again["run_id"] == run_id and again["cached"] is True
    assert len(client.engine.calls) == 1


def test_a_run_status_is_never_cached_by_the_browser(client):
    run_id = client.post("/runs", json=body()).json()["run_id"]
    assert client.get(f"/runs/{run_id}").headers["cache-control"] == "no-store"


@pytest.mark.parametrize("bad", [dict(level="8-4"), dict(mods=("keep_only",)), dict(from_moment="x"),
                                 dict(attachments={"no_such_sense": ["goomba"]})])
def test_refused_requests_are_422(client, bad):
    assert client.post("/runs", json=body(**bad)).status_code == 422


def test_a_malformed_body_is_422(client):
    assert client.post("/runs", json={"nonsense": 1}).status_code == 422


def test_unknown_run_and_video_are_404(client):
    assert client.get("/runs/abc123").status_code == 404
    assert client.get("/videos/abc123.mp4").status_code == 404
    assert client.get("/runs/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/videos/..%2Fsecret.mp4").status_code == 404
    assert client.get("/videos/abc123").status_code == 404


def test_rate_limit_is_429_with_retry_after(tmp_path):
    cfg = config(tmp_path, rate_per_minute=2)
    with TestClient(create_lite_app(cfg, engine=FakeEngine())) as c:
        codes = [c.post("/runs", json=body(max_frames=100 + i)).status_code for i in range(4)]
        assert codes == [202, 202, 429, 429]
        r = c.post("/runs", json=body(max_frames=999))
        assert int(r.headers["retry-after"]) >= 1


def test_busy_server_is_503(tmp_path):
    gate = threading.Event()
    cfg = config(tmp_path, queue_max=2, workers=1)
    with TestClient(create_lite_app(cfg, engine=FakeEngine(gate=gate))) as c:
        codes = [c.post("/runs", json=body(max_frames=100 + i)).status_code for i in range(3)]
        gate.set()
        assert codes == [202, 202, 503]


def test_forwarded_address_is_only_trusted_when_asked(tmp_path):
    for trust, expected in ((False, [202, 202, 429]), (True, [202, 202, 202])):
        cfg = config(tmp_path / str(trust), rate_per_minute=2, trust_proxy=trust)
        with TestClient(create_lite_app(cfg, engine=FakeEngine())) as c:
            codes = [c.post("/runs", json=body(max_frames=100 + i), headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
                     for i in range(3)]
            assert codes == expected


def test_cors_only_for_the_configured_origins(tmp_path):
    cfg = config(tmp_path, cors_origins=("https://me.github.io",))
    with TestClient(create_lite_app(cfg, engine=FakeEngine())) as c:
        ok = c.get("/health", headers={"Origin": "https://me.github.io"})
        bad = c.get("/health", headers={"Origin": "https://evil.example"})
        assert ok.headers["access-control-allow-origin"] == "https://me.github.io"
        assert "access-control-allow-origin" not in bad.headers


def test_no_download_evolution_or_save_routes_exist(client):
    paths = {r.path for r in client.app.routes}
    assert not any(p.startswith(("/jobs", "/videos/export", "/moments", "/flies/presets")) for p in paths)
    assert client.post("/jobs", json={}).status_code in (404, 405)
    assert client.put("/flies/blank", json={}).status_code == 405
    assert client.post("/flies", json={}).status_code in (404, 405)
