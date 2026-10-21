"""A real run through POST /runs + WS /runs/{id}/live (needs the connectome data and the emulator)."""
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from fly_mario.api.app import create_app
from fly_mario.runner import record
from fly_mario.runner.config import FLIES

pytestmark = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(record, "runs_dir", lambda: tmp_path / "runs")      # the moment store follows the runs folder
    shutil.copytree(FLIES, tmp_path / "flies")
    return TestClient(create_app(tmp_path / "flies", tmp_path / "runs"))


def start(client, **scene):
    fly = client.get("/flies/champion_e1s").json()
    return client.post("/runs", json={"fly": fly, "scene": {"level_id": "1-1", **scene}}).json()["id"]


def test_short_run_streams_separate_layers_and_controls_work(client):
    rid = start(client, noop=3, max_frames=40)
    with client.websocket_connect(f"/runs/{rid}/live") as ws:
        ws.send_json({"type": "speed", "value": 1000})
        frames, end, states = [], None, []
        while end is None:
            m = ws.receive_json()
            if m["type"] == "frame":
                frames.append(m)
            elif m["type"] == "state":
                states.append(m)
            elif m["type"] == "end":
                end = m
    assert len(frames) == 40 and end["result"]["outcome"] == "timeout"
    f = frames[0]
    assert f["frame_png"] and isinstance(f["overlay"], list) and "TTMn" in f["rates"] and "overlay" not in f["frame_png"]
    import base64
    assert base64.b64decode(f["frame_png"])[:8] == b"\x89PNG\r\n\x1a\n"
    assert any(s["speed"] == 1000 for s in states)
    assert client.get(f"/runs/{rid}").json()["status"] == "finished"
    assert rid in [r["id"] for r in client.get("/runs").json()]
    with client.websocket_connect(f"/runs/{rid}/live") as ws:               # a finished run replays its end
        assert ws.receive_json()["type"] == "end"


def test_pause_and_step(client):
    rid = start(client, max_frames=30)
    with client.websocket_connect(f"/runs/{rid}/live") as ws:
        ws.send_json({"type": "pause"})
        ws.send_json({"type": "speed", "value": 1000})
        seen = []
        while len(seen) < 2:                                                # acks for the two messages
            m = ws.receive_json()
            if m["type"] == "state":
                seen.append(m)
        assert seen[0]["paused"] is True
        ws.send_json({"type": "step"})
        types = []
        while "frame" not in types:
            types.append(ws.receive_json()["type"])
        ws.send_json({"type": "play"})
        while True:
            if ws.receive_json()["type"] == "end":
                break


def test_unknown_run_websocket_closes(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/runs/nope/live") as ws:
            ws.receive_json()


def test_champion_1_1_reaches_the_flag(client):
    rid = start(client, noop=3, sigma=0.05, seed=101)
    n = 0
    with client.websocket_connect(f"/runs/{rid}/live") as ws:
        ws.send_json({"type": "speed", "value": 1000})
        while True:
            m = ws.receive_json()
            n += m["type"] == "frame"
            if m["type"] == "end":
                break
    assert n > 100 and m["result"]["outcome"] == "flag"
    assert client.get(f"/runs/{rid}").json()["result"]["outcome"] == "flag"
