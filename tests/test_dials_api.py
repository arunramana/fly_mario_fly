"""Original vs tuned dials: every fly carries both, and a run can use either."""
import shutil

import pytest
from fastapi.testclient import TestClient

from fly_mario_fly.api import convert as V
from fly_mario_fly.api import knobs as K
from fly_mario_fly.api.app import create_app
from fly_mario_fly.runner import load_fly
from fly_mario_fly.runner.config import FLIES


@pytest.fixture
def client(tmp_path):
    flies = tmp_path / "flies"
    shutil.copytree(FLIES, flies)
    return TestClient(create_app(flies, tmp_path / "runs"))


def test_champion_overrides_every_knob_whose_default_is_the_original():
    """The original release threshold is the old hand-set 0.10; the champion keeps its evolved value."""
    specs = K.specs_by_key()
    assert specs["jump.release_thresh"].default == 0.10
    champ = load_fly(FLIES / "champion_e1s.yaml")
    assert "jump.release_thresh" in champ.knobs and champ.knobs["jump.release_thresh"] != 0.10


def test_fly_view_has_a_dial_per_knob_and_marks_the_tuned_ones(client):
    j = client.get("/flies/champion_e1s").json()
    assert set(j["dials"]) == set(K.specs_by_key())
    for key in ("home.drive", "hearing.gain", "sweet_smell.gain", "sour_smell.gain", "jump.ttmn_thresh",
                "jump.release_thresh", "steer.thresh", "back_up.mdn_thresh"):
        d = j["dials"][key]
        assert d["tuned"] and d["position"] == j["knobs"][key] and d["position"] != d["original_position"]
    assert not j["dials"]["walk.thresh"]["tuned"]                      # never evolved: sits at its original
    blank = client.get("/flies/blank").json()
    assert not any(d["tuned"] for d in blank["dials"].values())
    assert all(d["position"] == d["original_position"] for d in blank["dials"].values())


def test_original_dials_drop_every_knob_override():
    champ = load_fly(FLIES / "champion_e1s.yaml")
    assert V.with_dials(champ, "tuned") is champ
    orig = V.with_dials(champ, "original")
    assert orig.knobs == {} and orig.provenance["dials"] == "original" and orig.name == champ.name


def test_run_request_takes_dials_and_the_summary_says_which(client):
    fly = client.get("/flies/blank").json()
    scene = {"level_id": "1-1", "modifiers": [["whole_level", {}]]}
    r = client.post("/runs", json={"fly": fly, "scene": scene, "dials": "original"})
    assert r.status_code == 201 and r.json()["dials"] == "original"
    r = client.post("/runs", json={"fly": fly, "scene": scene})
    assert r.json()["dials"] == "tuned"                                # the default
    assert client.post("/runs", json={"fly": fly, "scene": scene, "dials": "bogus"}).status_code == 422
    assert {s["dials"] for s in client.get("/runs").json()} == {"original", "tuned"}
