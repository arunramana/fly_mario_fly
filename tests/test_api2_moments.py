"""The moment / resume / tries / level API, by API calls only (needs the connectome data and the emulator)."""
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from fly_mario_fly.api.app import create_app
from fly_mario_fly.runner import record
from fly_mario_fly.runner.config import FLIES

pytestmark = pytest.mark.skipif(not os.environ.get("FLY_MARIO_FLY_DATA"), reason="FLY_MARIO_FLY_DATA not set")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(record, "runs_dir", lambda: tmp_path / "runs")          # the moment store follows the runs folder
    shutil.copytree(FLIES, tmp_path / "flies")
    return TestClient(create_app(tmp_path / "flies", tmp_path / "runs"))


def play(client, rid, until=None):
    """Watch a run over its WebSocket at full speed; returns (frames, moment events, end or None if `until` stopped it)."""
    frames, moments = [], []
    with client.websocket_connect(f"/runs/{rid}/live") as ws:
        ws.send_json({"type": "speed", "value": 1000})
        while True:
            m = ws.receive_json()
            if m["type"] == "frame":
                frames.append(m)
                if until and until(m):
                    return frames, moments, None
            elif m["type"] == "moment":
                moments.append(m["moment"])
            elif m["type"] == "end":
                return frames, moments, m


def start(client, fly, **scene):
    return client.post("/runs", json={"fly": fly, "scene": {"level_id": "1-1", **scene}}).json()["id"]


def test_frames_carry_objects_and_scroll(client):
    fly = client.get("/flies/champion_e1s").json()
    frames, _, end = play(client, start(client, fly, noop=3, max_frames=400))
    assert end["result"]["outcome"] == "timeout" and len(frames) == 400
    assert {"goomba", "pipe"} <= {o["type"] for f in frames for o in f["objects"]}
    assert frames[0]["scroll_x"] == 0 < frames[-1]["scroll_x"]
    assert all(a["scroll_x_after"] == b["scroll_x"] for a, b in zip(frames, frames[1:]))
    f = next(f for f in frames if any(o["type"] == "goomba" for o in f["objects"]))
    g = next(o for o in f["objects"] if o["type"] == "goomba")
    assert set(g) == {"type", "id", "box", "side"} and g["box"]["w"] > 0


def test_manual_save_rename_delete_while_running(client):
    fly = client.get("/flies/champion_e1s").json()
    rid = start(client, fly, noop=3, max_frames=300)
    saved = []

    def save_at_30(f):
        if f["frame"] == 33:
            saved.append(client.post(f"/runs/{rid}/moments", json={"name": "start of walk"}))
        return bool(saved)

    play(client, rid, save_at_30)
    assert saved[0].status_code == 201, saved[0].text
    m = saved[0].json()
    assert m["name"] == "start of walk" and not m["auto"] and m["kind"] == "manual" and m["run_id"] == rid
    assert client.get(f"/moments/{m['id']}").json()["id"] == m["id"]
    assert [x["id"] for x in client.get(f"/runs/{rid}/moments").json()] == [m["id"]]
    assert client.patch(f"/moments/{m['id']}", json={"name": "renamed"}).json()["name"] == "renamed"
    assert client.get(f"/moments/{m['id']}/tries").json() == []
    assert client.delete(f"/moments/{m['id']}").status_code == 204
    assert client.get(f"/moments/{m['id']}").status_code == 404
    assert client.delete(f"/moments/{m['id']}").status_code == 404
    assert client.post("/runs/nope/moments", json={}).status_code == 404


def test_saving_a_moment_of_a_run_that_is_not_playing_is_refused(client):
    fly = client.get("/flies/champion_e1s").json()
    rid = start(client, fly, max_frames=5)
    assert client.post(f"/runs/{rid}/moments", json={}).status_code == 409        # still pending


def test_death_moment_resume_and_tries_end_to_end(client):
    fly = client.get("/flies/champion_e1s").json()
    scene = {"level_id": "1-2", "noop": 3, "sigma": 0.05, "seed": 101}
    rid = client.post("/runs", json={"fly": fly, "scene": scene}).json()["id"]
    _, events, end = play(client, rid)
    assert end["result"]["outcome"] == "died", end["result"]
    death = [m for m in client.get(f"/runs/{rid}/moments").json() if m["kind"] == "death"]
    assert len(death) == 1 and death[0]["name"] == "3 s before death" and death[0]["auto"]
    mid = death[0]["id"]
    assert mid in [m["id"] for m in events] and mid in end["result"]["moments"]    # also arrived as a moment event

    knob = "sour_smell.gain"
    stronger = {**fly, "knobs": {**fly["knobs"], knob: min(1.0, fly["knobs"][knob] + 0.25)}}
    new = client.post("/runs", json={"fly": stronger, "scene": scene, "from_moment": mid})
    assert new.status_code == 201 and new.json()["parent_moment"] == mid
    nid = new.json()["id"]
    _, _, end2 = play(client, nid)
    assert end2["result"]["parent_moment"] == mid
    assert client.get(f"/runs/{nid}").json()["parent_moment"] == mid

    tries = client.get(f"/moments/{mid}/tries").json()
    assert [t["run_id"] for t in tries] == [nid]
    t = tries[0]
    assert t["outcome"] == end2["result"]["outcome"] and "sour" in t["change"].lower() and "toward" in t["change"]
    assert not any(ch.isdigit() for ch in t["change"])                              # in words, no numbers
    wrong_level = {**scene, "level_id": "1-1"}
    assert client.post("/runs", json={"fly": fly, "scene": wrong_level, "from_moment": mid}).status_code == 422


def test_level_catalogue_reports_scan_status(client):
    lv = {x["id"]: x for x in client.get("/levels").json()}
    assert len(lv) == 35 and lv["2-2"]["kind"] == "water" and lv["1-1"]["status"] in ("open", "cleared")
    for x in lv.values():
        if x["objects"] is not None:
            assert x["objects"] == sorted(x["objects"])
