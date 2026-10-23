"""Dev set, evaluate(), and the background-job API. The emulator is replaced except in the one end-to-end test."""
import json
import re
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from fly_mario_fly.api import jobs as J
from fly_mario_fly.api.app import create_app
from fly_mario_fly.evolve import devset
from fly_mario_fly.runner import load_fly
from fly_mario_fly.runner.config import FLIES


# ---- the dev set -------------------------------------------------------------------------------------------------
def test_dev_set_1_1_is_the_old_holdout_10():
    starts = devset.dev_starts("1-1")
    assert len(starts) == 10
    assert [s["noop"] for s in starts] == [3, 11, 25, 33, 41] * 2
    assert [s["sigma"] for s in starts] == [0.0] * 5 + [0.05] * 5
    assert [s["seed"] for s in starts] == [101, 102, 103, 104, 105] * 2


def test_other_levels_use_the_default_set():
    assert devset.dev_starts("1-2") == devset.dev_starts("1-1")


def test_summary_counts_flags_and_means():
    eps = [{"outcome": "flag", "max_x": 3000.0, "score": 100.0}, {"outcome": "died", "max_x": 1000.0, "score": 0.0}]
    s = devset.summarize(eps)
    assert (s["flags"], s["n"], s["mean_max_x"], s["min_max_x"], s["mean_score"]) == (1, 2, 2000.0, 1000.0, 50.0)


class FakePool:
    def __init__(self):
        self.seen = []

    def map(self, jobs, on_done=None):
        self.seen += jobs
        out = [{"outcome": "flag" if j["scene"].noop < 20 else "died", "max_x": 100.0 * j["scene"].noop, "score": 1.0,
                "violations": 0, "frames": 5, "fitness": 0.5, "counts": {"a_onsets": 3, "left_presses": 1}, "blocks": 2,
                "mushroom": False, "death": None} for j in jobs]
        for i in range(len(jobs)):
            on_done and on_done(i + 1, len(jobs))
        return out


def test_evaluate_runs_each_start_and_original_resets_the_knobs():
    fly, pool, ticks = load_fly("champion_e1s"), FakePool(), []
    r = devset.evaluate(fly, "1-1", "original", pool=pool, on_done=lambda i, n: ticks.append((i, n)))
    assert len(r["episodes"]) == 10 and r["summary"]["n"] == 10 and r["summary"]["flags"] == 4      # noop 3 and 11, at both noise levels
    assert all(j["fly"].knobs == {} and j["fly"].provenance["dials"] == "original" for j in pool.seen)
    assert ticks[-1] == (10, 10)
    assert {"outcome", "max_x", "score", "counts", "start"} <= set(r["episodes"][0])
    tuned = devset.evaluate(fly, "1-1", "tuned", pool=FakePool())
    assert tuned["summary"]["n"] == 10


# ---- knob changes in words ---------------------------------------------------------------------------------------
def test_change_words_have_no_digits():
    from fly_mario_fly.api.knobs import specs_by_key
    spec = specs_by_key()["sour_smell.gain"]
    seen = set()
    for after in (spec.default, spec.default * 1.2, spec.default * 3, spec.hi, spec.lo):
        words, direction = J.change_words(spec, spec.default, after)
        assert not re.search(r"\d", words)
        seen.add(direction)
    assert seen == {"same", "hi", "lo"}


# ---- the job API, with the process launch stubbed ------------------------------------------------------------------
class FakeProc:
    pid = 0

    def poll(self):
        return None


def copy_presets(dst):
    """The preset flies only: a fly saved earlier by "Use this fly" (named *_evo_*) must not make the test's names collide."""
    shutil.copytree(FLIES, dst, ignore=shutil.ignore_patterns("*_evo_*"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    flies = tmp_path / "flies"
    copy_presets(flies)
    monkeypatch.setattr(J.subprocess, "Popen", lambda *a, **k: FakeProc())
    killed = []
    monkeypatch.setattr(J, "kill_tree", killed.append)
    c = TestClient(create_app(flies, tmp_path / "runs"))
    c.flies, c.runs, c.killed = flies, tmp_path / "runs", killed
    return c


def fly_json(client, name="champion_e1s"):
    return client.get(f"/flies/{name}").json()


def test_test_job_is_created_listed_and_cancelled(client):
    r = client.post("/jobs/test", json={"fly": fly_json(client), "level": "1-1"})
    assert r.status_code == 201
    jid = r.json()["id"]
    d = client.get(f"/jobs/{jid}").json()
    assert d["kind"] == "test" and d["status"] == "running" and d["dials"] == "both"
    assert [j["id"] for j in client.get("/jobs").json()] == [jid]
    (client.runs / jid / "progress.json").write_text(json.dumps({"phase": "testing", "done": 5, "total": 20, "eta_s": 30}))
    p = client.get(f"/jobs/{jid}").json()["progress"]
    assert (p["done"], p["total"], p["eta_s"]) == (5, 20, 30)
    c = client.post(f"/jobs/{jid}/cancel").json()
    assert c["status"] == "cancelled"
    assert client.get("/jobs/nope").status_code == 404


def test_a_silent_running_job_is_reported_interrupted(client):
    jid = client.post("/jobs/test", json={"fly": fly_json(client), "level": "1-1"}).json()["id"]
    job = json.loads((client.runs / jid / "job.json").read_text())
    job["created"] -= 3600
    (client.runs / jid / "job.json").write_text(json.dumps(job))
    d = client.get(f"/jobs/{jid}").json()
    assert d["status"] == "failed" and "interrupted" in d["error"]


def test_finished_test_job_reports_original_vs_tuned(client):
    jid = client.post("/jobs/test", json={"fly": fly_json(client), "level": "1-1"}).json()["id"]
    folder = client.runs / jid
    ep = {"outcome": "flag", "max_x": 3161.0, "score": 2275.0, "counts": {"a_onsets": 37, "left_presses": 10}, "blocks": 4,
          "mushroom": True, "death": None}
    res = {k: {"summary": {"flags": f, "n": 10, "mean_max_x": 3000.0, "min_max_x": 2000.0, "mean_score": 5.0},
               "episodes": [ep] * 10} for k, f in (("original", 8), ("tuned", 10))}
    (folder / "result.json").write_text(json.dumps({"results": res}))
    job = json.loads((folder / "job.json").read_text())
    (folder / "job.json").write_text(json.dumps({**job, "status": "finished"}))
    d = client.get(f"/jobs/{jid}").json()
    assert d["headline"] == "Original 8/10 · Tuned 10/10"
    assert d["results"]["tuned"]["episodes"][0]["jumps"] == 37 and d["results"]["tuned"]["episodes"][0]["back_ups"] == 10


def test_bad_requests(client):
    assert client.post("/jobs/test", json={"fly": fly_json(client), "level": "9-9"}).status_code == 422
    assert client.post("/jobs/evolve", json={"fly": fly_json(client), "start": "no-such-moment"}).status_code == 404
    assert client.post("/jobs/evolve", json={"fly": fly_json(client), "generations": 0}).status_code == 422


def test_use_saves_the_best_fly_with_provenance(client):
    jid = client.post("/jobs/evolve", json={"fly": fly_json(client), "generations": 2, "flag_x": 3161.0}).json()["id"]
    folder = client.runs / jid
    best = load_fly("champion_e1s")
    from dataclasses import replace

    from fly_mario_fly.runner import dump_fly
    prov = {"evolved_from": "champion_e1s", "generation": 1, "evolved": ["sour_smell.gain"], "evolution": jid}
    (folder / "start.yaml").write_text(dump_fly(best))
    (folder / "best.yaml").write_text(dump_fly(replace(best, name="champion_e1s_evo_k1",
                                                       knobs={**best.knobs, "sour_smell.gain": 10.0}, provenance=prov)))
    r = client.post(f"/jobs/{jid}/use")
    assert r.status_code == 201 and r.json()["name"] == "champion_e1s_evo_k1"
    assert r.json()["provenance"]["evolution"] == jid
    assert (client.flies / "champion_e1s_evo_k1.yaml").exists()
    assert client.post(f"/jobs/{jid}/use", json={"name": "champion_e1s_evo_k1"}).status_code == 409
    assert client.post(f"/jobs/{jid}/use", json={"name": "bad name!"}).status_code == 422
    assert client.post(f"/jobs/{jid}/use").json()["name"] == "champion_e1s_evo_k1_2"


# ---- the real thing: a tiny evolution through the API, in its own process, to the end -------------------------------
def test_tiny_evolution_runs_to_completion_with_progress(tmp_path):
    flies = tmp_path / "flies"
    copy_presets(flies)
    c = TestClient(create_app(flies, tmp_path / "runs"))
    fly = c.get("/flies/champion_e1s").json()
    jid = c.post("/jobs/evolve", json={"fly": fly, "level": "1-1", "generations": 2, "population": 4, "workers": 4,
                                       "train_n": 2, "flag_x": 3161.0}).json()["id"]
    seen, deadline = [], time.time() + 900
    try:
        while time.time() < deadline:
            d = c.get(f"/jobs/{jid}").json()
            seen.append((d["status"], d["progress"]["phase"], d["progress"]["generation"]))
            if d["status"] in ("finished", "failed", "cancelled"):
                break
            time.sleep(3)
    finally:
        c.post(f"/jobs/{jid}/cancel")
    assert d["status"] == "finished", (d["error"], seen)
    assert [b["gen"] for b in d["progress"]["bars"]] == [0, 1]
    assert {g for _, _, g in seen} >= {0, 2} and any(p == "training" for _, p, _ in seen)
    assert d["dev_best"]["n"] == 10 and d["dev_start"]["n"] == 10
    assert d["changes"] and not any(re.search(r"\d", ch["words"]) for ch in d["changes"])
    g = c.get(f"/jobs/{jid}/generations/1/fly")
    assert g.status_code == 200 and g.json()["name"].endswith("_gen1")
