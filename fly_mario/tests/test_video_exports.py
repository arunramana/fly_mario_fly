"""Video exports: the specs, the layouts, the API's two-stage flow (process launch stubbed) and one short real replay."""
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


def _test_job(runs, jid="test_1"):
    d = runs / jid
    d.mkdir(parents=True)
    (d / "job.json").write_text(json.dumps({"id": jid, "kind": "test", "status": "finished", "level": "1-1", "fly": "champion_e1s",
                                            "fly_config": _fly(), "dials": "both", "created": 1.0}), encoding="utf-8")
    ep = lambda o, x: {"start": {"noop": 3, "sigma": 0.0, "seed": 101}, "outcome": o, "max_x": x, "frames": 1295}   # noqa: E731
    (d / "result.json").write_text(json.dumps({"results": {"original": {"episodes": [ep("died", 2003.0)]},
                                                           "tuned": {"episodes": [ep("flag", 3161.0)]}}}), encoding="utf-8")
    return jid


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
def test_test_side_is_the_start_at_that_dials_and_checks_against_the_test(tmp_path):
    jid = _test_job(tmp_path)
    o, t = Sp.test_side(jid, 1, "original", tmp_path), Sp.test_side(jid, 1, "tuned", tmp_path)
    assert o["scene"] == t["scene"] and (o["scene"]["noop"], o["scene"]["seed"]) == (3, 101)
    assert o["fly"]["knobs"] == {} and Sp.dials_of(o["fly"]) == "original" and Sp.dials_of(t["fly"]) == "tuned"
    assert (o["expect"]["outcome"], o["expect"]["max_x"], o["expect"]["frames"]) == ("died", 2003.0, 1295)
    with pytest.raises(ValueError):
        Sp.test_side(jid, 2, "tuned", tmp_path)


def test_default_labels_are_the_dials_then_the_fly_names():
    a, b = {"fly": _fly("original")}, {"fly": _fly()}
    assert Sp.side_labels(a, b) == ("Original dials", "Tuned dials")
    assert Sp.side_labels(a, {"fly": _fly(evolved=True)}) == ("Original dials", "Tuned dials (evolved)")
    assert Sp.side_labels(a, b, "Before", "") == ("Before", "Tuned dials")
    other = {"fly": {**_fly(), "name": "other"}}
    assert Sp.side_labels(b, other) == ("champion_e1s", "other")
    assert Sp.side_labels(b, b) == ("champion_e1s (1)", "champion_e1s (2)")


def test_side_by_side_needs_the_same_start(tmp_path):
    _saved(tmp_path, "a")
    _saved(tmp_path, "b", scene={**SCENE, "seed": 7})
    with pytest.raises(ValueError, match="same place"):
        Sp.side_by_side_spec(Sp.saved_side("a", tmp_path), Sp.saved_side("b", tmp_path))


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
    few = Sp.montage_spec(eid, gens=[2], include_start=True, root=tmp_path)
    assert [x["label"] for x in few["sides"]] == ["Starting fly", "Generation 2"]
    with pytest.raises(ValueError):
        Sp.montage_spec(eid, gens=[9], root=tmp_path)


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


def _spec(n_a, n_b, **kw):
    return {"export": "side_by_side", "show_senses": True, "show_brain": False, "speed": 1,
            "sides": [{"label": "Original dials", "n": n_a, "outcome": "died", "caption": "Died at x 5", "expect": {"frames": n_a}},
                      {"label": "Tuned dials", "n": n_b, "outcome": "flag", "caption": "Reached the flag", "expect": {"frames": n_b}}], **kw}


def test_side_by_side_freezes_the_shorter_run_and_holds_the_end(monkeypatch):
    monkeypatch.setattr(X, "Lane", FakeLane)
    ex = X.SideBySideExport(_spec(4, 10))
    out = list(ex.frames())
    assert len(out) == 10 + int(X.HOLD_S * X.FPS)
    img = out[-1][1]
    assert img.shape == (1080, 1920, 3)
    left, right = ex.X
    # the left game was frozen on its last frame (index 3) while the right one played on to index 9
    assert out[3][1][ex.game_y + 100, left + 100, 0] == out[9][1][ex.game_y + 100, left + 100, 0] == 3
    assert out[9][1][ex.game_y + 100, right + 100, 0] == 9
    assert not np.array_equal(out[2][1][ex.cap_y:ex.cap_y + 48], out[3][1][ex.cap_y:ex.cap_y + 48])      # the caption appears when it ends


def test_side_by_side_speed_2_keeps_the_frame_where_a_run_ends(monkeypatch):
    monkeypatch.setattr(X, "Lane", FakeLane)
    spec = _spec(4, 9)
    spec["speed"] = 2
    n = len(list(X.SideBySideExport(spec).frames())) - int(X.HOLD_S * X.FPS)
    assert n == 6                                                   # steps 0, 2, 3 (a run ends), 4, 6, 8


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
    stills = list(X.MontageExport(spec).frames(picks=[0, 2]))
    assert [k for k, _ in stills] == [0, 2]


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


def _finish(client, vid, stage, **files):
    folder = client.videos / vid
    job = json.loads((folder / "job.json").read_text())
    (folder / "job.json").write_text(json.dumps({**job, "stage": stage, "status": "finished"}))
    for name, data in files.items():
        p = folder / name
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(data) if isinstance(data, bytes) else p.write_text(json.dumps(data))


def test_run_video_is_stills_first_then_render_then_download(client):
    _saved(client.runs, "run1")
    r = client.post("/videos", json={"export": "run", "run_id": "run1", "show_brain": False, "speed": 2})
    assert r.status_code == 201
    v = r.json()
    vid = v["id"]
    assert (v["export"], v["stage"], v["status"], v["stills"], v["video"]) == ("run", "stills", "running", [], None)
    spec = json.loads((client.videos / vid / "job.json").read_text())["spec"]
    assert (spec["show_brain"], spec["speed"], spec["show_senses"]) == (False, 2, True)

    assert client.post(f"/videos/{vid}/render").status_code == 409                      # still making the stills
    _finish(client, vid, "stills", **{"stills.json": {"stills": ["still_1.png", "still_2.png"]}, "stills/still_1.png": b"\x89PNG1", "stills/still_2.png": b"\x89PNG2"})
    v = client.get(f"/videos/{vid}").json()
    assert v["status"] == "finished" and v["stills"] == [f"/videos/{vid}/stills/1.png", f"/videos/{vid}/stills/2.png"] and v["video"] is None
    assert client.get(v["stills"][1]).content == b"\x89PNG2"
    assert client.get(f"/videos/{vid}/video.mp4").status_code == 404                    # nothing rendered before the user asks

    r = client.post(f"/videos/{vid}/render").json()
    assert r["stage"] == "video" and r["status"] == "running"
    _finish(client, vid, "video", **{"video.mp4": b"MP4DATA", "info.json": {"file": "video.mp4", "duration_s": 12.5, "bytes": 2_000_000, "render_s": 9.0,
            "replay_checks": [{"label": "run1", "outcome": "flag", "max_x": 500.0, "hash_ok": True}]}})
    v = client.get(f"/videos/{vid}").json()
    assert v["video"] == f"/videos/{vid}/video.mp4" and v["duration_s"] == 12.5 and v["checks"][0]["hash_ok"] is True
    assert client.get(v["video"]).content == b"MP4DATA"
    assert "attachment" in client.get(v["video"] + "?download=true").headers["content-disposition"]
    assert [x["id"] for x in client.get("/videos").json()] == [vid]


def test_side_by_side_and_montage_requests(client):
    jid = _test_job(client.runs)
    r = client.post("/videos", json={"export": "side_by_side", "a": {"job_id": jid, "start": 1, "dials": "original"},
                                     "b": {"job_id": jid, "start": 1, "dials": "tuned"}})
    assert r.status_code == 201 and "Original dials" in r.json()["title"] and "Tuned dials" in r.json()["title"]
    spec = json.loads((client.videos / r.json()["id"] / "job.json").read_text())["spec"]
    assert spec["show_brain"] is False and [s["label"] for s in spec["sides"]] == ["Original dials", "Tuned dials"]
    eid = _evolution(client.runs)
    m = client.post("/videos", json={"export": "montage", "job_id": eid, "generations": [0, 2], "clip_seconds": 4})
    assert m.status_code == 201
    mspec = json.loads((client.videos / m.json()["id"] / "job.json").read_text())["spec"]
    assert (mspec["speed"], [s["label"] for s in mspec["sides"]]) == (2, ["Generation 0", "Generation 2"])


def test_bad_video_requests_are_422(client):
    _saved(client.runs, "a")
    _saved(client.runs, "b", scene={**SCENE, "noop": 9})
    for body in ({"export": "run"}, {"export": "run", "run_id": "nope"}, {"export": "side_by_side"},
                 {"export": "side_by_side", "a": {"run_id": "a"}, "b": {"run_id": "b"}},
                 {"export": "montage"}, {"export": "montage", "job_id": "nope"}, {"export": "run", "run_id": "a", "speed": 3}):
        assert client.post("/videos", json=body).status_code == 422, body
    assert client.get("/videos/nope").status_code == 404 and client.post("/videos/nope/render").status_code == 404


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
def test_real_side_by_side_replays_two_runs_of_the_same_start(tmp_path):
    """Original vs Tuned from one start, stopped after 40 frames: both lanes run through the real runner."""
    scene = {**SCENE, "max_frames": 40}
    spec = Sp.side_by_side_spec({"run_id": "", "fly": _fly("original"), "scene": scene, "options": {}, "expect": {"frames": 40}},
                                {"run_id": "", "fly": _fly(), "scene": scene, "options": {}, "expect": {"frames": 40}})
    ex = X.SideBySideExport(spec)
    out = list(ex.frames(picks=[-1]))
    assert [k for k, _ in out] == [-1] and out[0][1].shape == (1080, 1920, 3)
    assert [c["outcome"] for c in ex.report] == ["timeout", "timeout"]
    folder = X.new_job_folder(spec, "t", tmp_path)
    info = X.make_stills(folder, spec)
    assert len(info["stills"]) == 3 and all((folder / "stills" / f).exists() for f in info["stills"])
    assert Sp.title(spec) == "Side by side: Original dials and Tuned dials"
