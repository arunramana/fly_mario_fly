"""Video exports (a run, a montage): the specs, the layouts, the API's one-step flow (process launch stubbed) and one short real replay."""
import json
import shutil
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

from fly_mario.api import videos as VD
from fly_mario.api.app import create_app
from fly_mario.render import export as X
from fly_mario.render import specs as Sp
from fly_mario.runner import fly_to_dict, load_fly
from fly_mario.runner.config import FLIES

SCENE = {"level_id": "1-1", "rom": "v0", "modifiers": [], "start": "level_start", "noop": 3, "sigma": 0.0, "seed": 101,
         "max_frames": 3000, "stuck_frames": 150}


def _fly(dials="tuned", evolved=False):
    f = fly_to_dict(load_fly("champion_e1s"))
    if dials == "original":
        f["knobs"], f["provenance"] = {}, {"dials": "original"}
    elif evolved:
        f["provenance"] = {"evolution": "evo_x"}
    return f


def _saved(runs, rid, outcome="flag", frames=100, dials="tuned", scene=None):
    d = runs / rid
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(yaml.safe_dump({"fly": _fly(dials), "scene": scene or SCENE, "options": {}}), encoding="utf-8")
    (d / "summary.json").write_text(json.dumps({"id": rid, "fly": "champion_e1s", "level": "1-1", "outcome": outcome, "max_x": 500.0,
                                                "score": 1.0, "counts": {"frames": frames}, "hash": "abc", "death": None}), encoding="utf-8")


def _evolution(runs, eid="evo_1", gens=3):
    d = runs / eid
    d.mkdir(parents=True)
    fly = load_fly("champion_e1s")
    (d / "job.json").write_text(json.dumps({"id": eid, "kind": "evolve", "status": "finished", "level": "1-1", "start": "level_start",
                                            "created": 1.0}), encoding="utf-8")
    (d / "start.yaml").write_text(yaml.safe_dump(fly_to_dict(fly)), encoding="utf-8")
    rows = [{"gen": g, "best": 0.5 + g * 0.1, "mean": 0.3 + g * 0.05, "best_values": {"sour_smell.gain": 5.0 + g}} for g in range(-1, gens)]
    (d / "progress.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return eid


# ---- specs ---------------------------------------------------------------------------------------------------------
def test_run_spec_clamps_and_validates_the_frame_range(tmp_path):
    _saved(tmp_path, "a", frames=100)
    s = Sp.run_spec("a", speed=2, frame_from=0, frame_to=10_000, root=tmp_path)
    assert (s["frame_from"], s["frame_to"], s["speed"]) == (3, 102, 2)            # noop 3 + 100 frames
    with pytest.raises(ValueError):
        Sp.run_spec("a", frame_from=50, frame_to=20, root=tmp_path)
    with pytest.raises(ValueError):
        Sp.run_spec("a", speed=3, root=tmp_path)
    with pytest.raises(ValueError):
        Sp.run_spec("../a", root=tmp_path)


def test_montage_spec_has_a_clip_per_generation_with_its_knobs(tmp_path):
    eid = _evolution(tmp_path)
    s = Sp.montage_spec(eid, root=tmp_path)
    assert [x["label"] for x in s["sides"]] == ["Generation 0", "Generation 1", "Generation 2"]
    assert [x["fly"]["knobs"]["sour_smell.gain"] for x in s["sides"]] == [5.0, 6.0, 7.0]
    assert [b["gen"] for b in s["bars"]] == [0, 1, 2]
    assert s["show_brain"] is True and s["speed"] == 2
    with pytest.raises(ValueError):
        Sp.montage_spec("nope", root=tmp_path)


# ---- how a run is worded ---------------------------------------------------------------------------------------------
def test_outcome_text_is_factual():
    run = lambda **k: SimpleNamespace(outcome="died", max_x=891.0, death=None, **k)    # noqa: E731
    assert X.outcome_text(SimpleNamespace(outcome="flag", max_x=3161.0, death=None)) == "Reached the flag"
    assert X.outcome_text(run()) == "Died at x 891"
    d = SimpleNamespace(outcome="died", max_x=891.0, death={"x": 891, "cause": "enemy:koopa"})
    assert X.outcome_text(d) == "Died at x 891 · Koopa"
    assert X.outcome_text(SimpleNamespace(outcome="stuck", max_x=700.2, death=None)) == "Got stuck at x 700"
    assert X.outcome_text(SimpleNamespace(outcome="timeout", max_x=700.0, death=None)) == "Ran out of time at x 700"


# ---- the layouts, on synthetic lanes ------------------------------------------------------------------------------------
class FakeLane:
    """A lane that plays `n` frames of a flat colour and then ends."""

    def __init__(self, side, n=None):
        self.side, self.n, self.index, self.ended, self.caption = side, side["n"], -1, False, ""
        self.run = SimpleNamespace(outcome=side["outcome"])
        self.fd = None

    def advance(self):
        if self.ended:
            return False
        self.index += 1
        self.fd = SimpleNamespace(game=np.full((240, 256, 3), self.index % 250, np.uint8), overlay=[], scroll_x=0.0, rates={}, frame=self.index)
        if self.index + 1 >= self.n:
            self.ended, self.caption = True, self.side["caption"]
        return True

    def check(self):
        return {"label": "", "run_id": "", "outcome": "", "max_x": 0, "frames": 0, "hash": "", "hash_ok": None, "matches_test": None}


def test_montage_clips_are_one_per_generation_with_the_current_one_marked(monkeypatch):
    monkeypatch.setattr(X, "Lane", FakeLane)
    spec = {"export": "montage", "speed": 1, "clip_seconds": 1.0, "show_senses": True, "show_brain": False,
            "bars": [{"gen": g, "best": 1 + g, "mean": 0.5 + g * 0.5} for g in range(3)],
            "sides": [{"label": f"Generation {g}", "gen": g, "n": 10_000, "outcome": "died", "caption": "", "expect": {}} for g in range(3)]}
    ex = X.MontageExport(spec)
    frames = list(ex.frames())
    assert [k for k, _ in frames].count(0) == [k for k, _ in frames].count(1) == 60 and len(frames) == 180
    assert not np.array_equal(frames[0][1][950:1050], frames[-1][1][950:1050])      # the fitness strip highlights a different generation
    assert frames[0][1].shape == (1080, 1920, 3)
    assert X.MontageExport({**spec, "show_brain": True}).GAME_X == 896 + (1920 - 896 - 768) // 2          # the brain panel takes the left 896 px


def test_writer_makes_an_h264_mp4(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    w = X.Writer(tmp_path / "t.mp4")
    for i in range(5):
        w.write(np.full((1080, 1920, 3), i * 40, np.uint8))
    w.close()
    assert (tmp_path / "t.mp4").stat().st_size > 1000


# ---- the API: two stages, process launch stubbed -------------------------------------------------------------------------------
class FakeProc:
    pid = 0

    def poll(self):
        return None


@pytest.fixture
def client(tmp_path, monkeypatch):
    flies = tmp_path / "flies"
    shutil.copytree(FLIES, flies)
    monkeypatch.setattr(VD.subprocess, "Popen", lambda *a, **k: FakeProc())
    killed = []
    monkeypatch.setattr(VD, "kill_tree", killed.append)
    c = TestClient(create_app(flies, tmp_path / "runs"))
    c.runs, c.videos, c.killed = tmp_path / "runs", tmp_path / "videos", killed
    c.runs.mkdir()
    return c


def _finish(client, vid, **files):
    folder = client.videos / vid
    job = json.loads((folder / "job.json").read_text())
    (folder / "job.json").write_text(json.dumps({**job, "status": "finished"}))
    for name, data in files.items():
        p = folder / name
        p.write_bytes(data) if isinstance(data, bytes) else p.write_text(json.dumps(data))


def test_run_video_renders_at_once_then_downloads(client):
    _saved(client.runs, "run1")
    r = client.post("/videos", json={"export": "run", "run_id": "run1", "show_brain": False})
    assert r.status_code == 201
    v = r.json()
    vid = v["id"]
    assert (v["export"], v["of"], v["status"], v["video"]) == ("run", "run1", "running", None)
    spec = json.loads((client.videos / vid / "job.json").read_text())["spec"]
    assert (spec["show_brain"], spec["speed"], spec["show_senses"]) == (False, 1, True)
    assert client.get(f"/videos/{vid}/video.mp4").status_code == 404                    # not rendered yet
    assert "stills" not in v and client.post(f"/videos/{vid}/render").status_code in (404, 405)

    _finish(client, vid, **{"video.mp4": b"MP4DATA", "info.json": {"file": "video.mp4", "duration_s": 12.5, "bytes": 2_000_000, "render_s": 9.0,
            "replay_checks": [{"label": "run1", "outcome": "flag", "max_x": 500.0, "hash_ok": True}]}})
    v = client.get(f"/videos/{vid}").json()
    assert v["video"] == f"/videos/{vid}/video.mp4" and v["duration_s"] == 12.5 and v["checks"][0]["hash_ok"] is True
    plain, dl = client.get(v["video"]), client.get(v["video"] + "?download=true")
    assert plain.content == b"MP4DATA" and plain.headers["content-type"] == "video/mp4"
    assert dl.headers["content-disposition"].startswith("attachment") and f"{vid}.mp4" in dl.headers["content-disposition"]
    assert [x["id"] for x in client.get("/videos").json()] == [vid]


def test_montage_request(client):
    eid = _evolution(client.runs)
    m = client.post("/videos", json={"export": "montage", "job_id": eid})
    assert m.status_code == 201 and m.json()["of"] == eid
    mspec = json.loads((client.videos / m.json()["id"] / "job.json").read_text())["spec"]
    assert (mspec["speed"], [s["label"] for s in mspec["sides"]]) == (2, ["Generation 0", "Generation 1", "Generation 2"])


def test_bad_video_requests_are_422(client):
    _saved(client.runs, "a")
    for body in ({"export": "run"}, {"export": "run", "run_id": "nope"}, {"export": "side_by_side"},
                 {"export": "montage"}, {"export": "montage", "job_id": "nope"}):
        assert client.post("/videos", json=body).status_code == 422, body
    assert client.get("/videos/nope").status_code == 404


def test_cancel_stops_the_process_and_removes_the_partial_file(client):
    _saved(client.runs, "run1")
    vid = client.post("/videos", json={"export": "run", "run_id": "run1"}).json()["id"]
    job = json.loads((client.videos / vid / "job.json").read_text())
    (client.videos / vid / "job.json").write_text(json.dumps({**job, "pid": 4242}))
    part = client.videos / vid / "video.part.mp4"
    part.write_bytes(b"half")
    assert client.post(f"/videos/{vid}/cancel").json()["status"] == "cancelled"
    assert client.killed == [4242] and not part.exists()


# ---- one short real replay -------------------------------------------------------------------------------------------------------------------
def test_real_run_video_replays_and_writes_an_mp4(tmp_path):
    """A run stopped after 40 frames goes through the real runner and the encoder."""
    pytest.importorskip("imageio_ffmpeg")
    scene = {**SCENE, "max_frames": 40}
    side = {"run_id": "", "fly": _fly(), "scene": scene, "options": {}, "label": "", "rates": "", "expect": {"frames": 40}}
    spec = {"export": "run", "sides": [side], "show_senses": True, "show_brain": False, "speed": 1, "frame_from": 3, "frame_to": 42}
    folder = X.new_job_folder(spec, "t", tmp_path)
    info = X.make_video(folder, spec)
    assert (folder / "video.mp4").stat().st_size > 1000 and info["frames"] > 30
    assert [c["outcome"] for c in info["replay_checks"]] == ["timeout"]
