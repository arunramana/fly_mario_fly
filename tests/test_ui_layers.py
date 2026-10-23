"""The UI lane: the picture layers of the live stream, the level catalogue as the browser sees it, level thumbnails."""
import base64
import os
import shutil

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from fly_mario.api import convert as V
from fly_mario.api import layers as L
from fly_mario.api.app import create_app
from fly_mario.runner import record
from fly_mario.runner.config import FLIES

needs_data = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")

def test_png_bytes_round_trip_rgb_and_rgba():
    for ch in (3, 4):
        img = np.random.default_rng(ch).integers(0, 256, (17, 23, ch), dtype=np.uint8)
        back = cv2.imdecode(np.frombuffer(L.png_bytes(img), np.uint8), cv2.IMREAD_UNCHANGED)
        assert back.shape[:2] == (17, 23)
        rgb = cv2.cvtColor(back, cv2.COLOR_BGRA2RGBA if ch == 4 else cv2.COLOR_BGR2RGB)
        assert np.array_equal(rgb, img)


def test_level_labels_and_order():
    assert V.LEVEL_ORDER[:5] == ["1-1", "1-2", "1-3", "1-4", "2-1"] and V.LEVEL_ORDER[31] == "8-4"
    assert V.LEVEL_ORDER[32:] == ["full", "lost_levels", "random"]
    assert V.LEVEL_NAMES == {"full": "Whole game", "lost_levels": "Lost Levels", "random": "Random Stages"}


@needs_data
def test_catalogue_thumbnails_and_start_screens(tmp_path, monkeypatch):
    from fly_mario.mario.env import MarioEnv
    from fly_mario.runner import levels
    monkeypatch.setattr(record, "runs_dir", lambda: tmp_path / "runs")
    client = TestClient(create_app(tmp_path / "flies", tmp_path / "runs"))
    cat = client.get("/levels").json()
    assert [c["id"] for c in cat] == V.LEVEL_ORDER
    assert [c["label"] for c in cat[32:]] == ["Whole game", "Lost Levels", "Random Stages"]
    # every kind in the catalogue is what the emulator says the stage is (area type, RAM 0x074E)
    names = {0: "water", 1: "overground", 2: "underground", 3: "castle"}
    env = MarioEnv()
    for c in cat:
        if c["id"] == "random":
            assert c["kind"] == "mixed"
            continue
        env.reset(c["id"], "v0", 0)
        assert names[int(env.ram[0x74E])] == {"athletic": "overground"}.get(c["kind"], c["kind"]), c["id"]   # athletic = overground sky levels
        if "-" in c["id"]:
            assert (int(env.ram[0x75F]) + 1, int(env.ram[0x75C]) + 1) == tuple(map(int, c["id"].split("-"))), c["id"]
    env.close()
    r = client.get("/levels/2-2/thumbnail.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape == (208, 256, 3)
    assert client.get("/levels/9-9/thumbnail.png").status_code == 404
    assert levels.level_thumbnail("random")[:4] == b"\x89PNG"


@needs_data
def test_live_frames_carry_the_layers(tmp_path, monkeypatch):
    monkeypatch.setattr(record, "runs_dir", lambda: tmp_path / "runs")
    shutil.copytree(FLIES, tmp_path / "flies")
    client = TestClient(create_app(tmp_path / "flies", tmp_path / "runs"))
    fly = client.get("/flies/champion_e1s").json()
    rid = client.post("/runs", json={"fly": fly, "scene": {"level_id": "1-1", "noop": 3, "max_frames": 150}}).json()["id"]
    frames = []
    with client.websocket_connect(f"/runs/{rid}/live") as ws:
        ws.send_json({"type": "speed", "value": 1000})
        while True:
            m = ws.receive_json()
            if m["type"] == "frame":
                frames.append(m)
            elif m["type"] == "end":
                break
    assert len(frames) == 150
    with_overlay = [f for f in frames if f["overlay"]]
    assert with_overlay, "the champion's senses draw something in 150 frames"
    f = with_overlay[0]
    assert {"kind", "geometry", "colour", "line", "anchor"} <= set(f["overlay"][0]) and "scroll_x" in f
    assert all("overlay_png" not in fr and "overlay_at" not in fr for fr in frames)       # the browser draws the overlay
    brains = [f["brain_jpg"] for f in frames if f["brain_jpg"]]
    assert brains, "a brain picture arrives within 150 frames"
    jpg = cv2.imdecode(np.frombuffer(base64.b64decode(brains[0]), np.uint8), cv2.IMREAD_COLOR)
    assert jpg.shape == (1080, 896, 3)
    r = client.post("/brain-map.png", json=fly)
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
