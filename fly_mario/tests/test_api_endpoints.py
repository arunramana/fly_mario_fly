"""The API over TestClient: every endpoint, plug-ins appear by themselves, no raw knob value ever leaves."""
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from fly_mario import registry
from fly_mario.api import knobs as K
from fly_mario.api.app import OPENAPI_PATH, create_app
from fly_mario.contracts import KnobSpec
from fly_mario.runner.config import FLIES


@pytest.fixture
def client(tmp_path):
    flies = tmp_path / "flies"
    shutil.copytree(FLIES, flies)
    c = TestClient(create_app(flies, tmp_path / "runs"))
    c.flies = flies
    return c


RAW_KEYS = {"default", "lo", "hi", "floor"}


def walk(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k, v
            yield from walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)


def test_registry_lists_every_kind_and_no_raw_knob(client):
    r = client.get("/registry")
    assert r.status_code == 200
    j = r.json()
    assert {"objects", "senses", "shapes", "actions", "scene_modifiers", "test_scenes", "presets"} <= set(j)
    assert j["objects"] and j["senses"] and j["actions"] and j["shapes"]
    knobs = [k for s in j["senses"] + j["actions"] + j["shapes"] for k in s["knobs"]]
    assert knobs
    for k in knobs:
        assert RAW_KEYS.isdisjoint(k) and 0 <= k["position"] <= 1 and k["lo_label"] and k["hi_label"]
    assert any(m["per_object"] for m in j["scene_modifiers"])
    assert len(j["test_scenes"]) >= len(j["objects"])          # one per object per object-picking modifier


def test_registry_knob_values_do_not_appear_as_numbers(client):
    """The raw defaults/ranges of every plug-in knob must not be anywhere in the registry response."""
    text = client.get("/registry").text
    checked = 0
    for plugins in (registry.list_plugins(k) for k in ("senses", "actions", "shapes")):
        for p in plugins.values():
            for k in p.knobs:
                for raw in (k.lo, k.hi, k.default):
                    if not 0 <= raw <= 1:                       # outside 0..1 it cannot be mistaken for a position
                        checked += 1
                        assert repr(float(raw)) not in text and str(raw) not in text.replace(" ", ""), (k.key, raw)
    assert checked
    j = json.loads(text)
    assert not any(RAW_KEYS & set(kn) for e in j["senses"] + j["actions"] + j["shapes"] for kn in e["knobs"])


def test_dummy_plugins_appear_in_registry(client, monkeypatch):
    class Dummy:
        name, label, note, kind, default_loom_shape = "dummy_obj", "Dummy", "n", "enemy", "own_box"

    class DummySense:
        name, label, effect, scope, colour, line = "dummy_sense", "Dummy sense", "e", "per_object", "#fff", "dotted"
        feeds = []
        knobs = [KnobSpec("dummy.k", "K", "low", "high", 5.0, 1.0, 100.0, scale="log")]

    real = registry.list_plugins

    def patched(kind):
        out = dict(real(kind))
        if kind == "objects":
            out["dummy_obj"] = Dummy()
        if kind == "senses":
            out["dummy_sense"] = DummySense()
        return out

    monkeypatch.setattr(registry, "list_plugins", patched)
    j = client.get("/registry").json()
    assert "dummy_obj" in [o["name"] for o in j["objects"]]
    s = next(s for s in j["senses"] if s["name"] == "dummy_sense")
    assert s["knobs"][0]["position"] == pytest.approx(K.to_position(DummySense.knobs[0], 5.0))
    assert any(t["name"].endswith(":dummy_obj") for t in j["test_scenes"])


def test_knob_position_roundtrip():
    for spec in (KnobSpec("a", "", "", "", 1.0, 0.0, 4.0), KnobSpec("b", "", "", "", 1.0, 0.25, 4.0, scale="log")):
        assert K.from_position(spec, 0) == spec.lo and K.from_position(spec, 1) == spec.hi
        for v in (spec.lo, 1.0, spec.hi):
            assert K.from_position(spec, K.to_position(spec, v)) == pytest.approx(v)
    assert K.to_position(KnobSpec("b", "", "", "", 1.0, 0.25, 4.0, scale="log"), 1.0) == pytest.approx(0.5)


def test_levels(client):
    levels = client.get("/levels").json()
    assert len(levels) == 35 and levels[0]["id"] == "1-1"
    one = client.get("/levels/1-1").json()
    assert one["id"] == "1-1" and one["kind"] == "overground" and one["status"] in ("open", "cleared")
    assert {"scanned", "partial", "width", "objects", "status_text"} <= set(one)
    assert client.get("/levels/9-9").status_code == 404


def test_flies_list_get_presets_and_no_raw_values(client):
    names = [f["name"] for f in client.get("/flies").json()]
    assert "champion_e1s" in names
    fly = client.get("/flies/champion_e1s").json()
    assert fly["knobs"] and all(0 <= v <= 1 for v in fly["knobs"].values())
    assert fly["knobs"]["sweet_smell.gain"] != 401.53277913051306
    presets = client.get("/flies/presets").json()
    assert {p["name"] for p in presets} == set(names)
    assert client.get("/flies/nope").status_code == 404


def test_fly_post_put_roundtrip_through_the_runner(client):
    fly = client.get("/flies/champion_e1s").json()
    fly["name"] = "mine"
    fly["knobs"] = {"home.drive": 0.25}
    r = client.post("/flies", json=fly)
    assert r.status_code == 201 and r.json()["knobs"]["home.drive"] == pytest.approx(0.25)
    assert client.post("/flies", json=fly).status_code == 409
    from fly_mario.runner import load_fly
    spec = K.specs_by_key()["home.drive"]
    assert load_fly(client.flies / "mine.yaml").knobs["home.drive"] == pytest.approx(K.from_position(spec, 0.25))
    fly["knobs"]["home.drive"] = 0.75
    assert client.put("/flies/mine", json=fly).json()["knobs"]["home.drive"] == pytest.approx(0.75)
    assert client.put("/flies/other", json=fly).status_code == 422          # path/body name mismatch
    assert client.put("/flies/ghost", json={**fly, "name": "ghost"}).status_code == 404
    bad = {**fly, "name": "bad", "knobs": {"no.such": 0.5}}
    assert client.post("/flies", json=bad).status_code == 422
    assert client.post("/flies", json={**fly, "name": "bad", "knobs": {"home.drive": 1.5}}).status_code == 422
    assert client.post("/flies", json={**fly, "name": "../x"}).status_code == 422


def test_runs_validation_and_listing(client):
    fly = client.get("/flies/champion_e1s").json()
    scene = {"level_id": "1-1", "max_frames": 10}
    r = client.post("/runs", json={"fly": fly, "scene": scene})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    rid = r.json()["id"]
    assert rid in [x["id"] for x in client.get("/runs").json()]
    d = client.get(f"/runs/{rid}").json()
    assert d["scene"]["max_frames"] == 10 and d["result"] is None
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/runs", json={"fly": fly, "scene": {"level_id": "9-9"}}).status_code == 422
    assert client.post("/runs", json={"fly": fly, "scene": {**scene, "modifiers": [["ghost", {}]]}}).status_code == 422
    assert client.post("/runs", json={"fly": fly, "scene": scene, "from_moment": "x@1"}).status_code == 404
    assert client.get(f"/runs/{rid}/moments").json() == []
    assert client.get("/runs/nope/moments").status_code == 404


def test_openapi_file_is_current():
    assert json.loads(OPENAPI_PATH.read_text(encoding="utf-8")) == create_app().openapi()
    comps = create_app().openapi()["components"]["schemas"]
    assert {"FrameEvent", "EndEvent", "ClientMessage", "RunEvent"} <= set(comps)
