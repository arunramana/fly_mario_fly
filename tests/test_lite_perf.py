"""Lite server with the real engine: the same run as the full tool, and inside its time, memory and disk budgets.

Needs the MaleCNS data once, to export the brains into a bundle; the runs themselves are made in a subprocess that has no data
folder at all, which is how the lite server runs. Budgets are set about 3x above what a laptop measures; on a slow machine
scale them with FMF_PERF_SLACK=2.
"""
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lite_support import request

from fly_mario_fly.api import convert as V
from fly_mario_fly.lite import bundle
from fly_mario_fly.lite.app import create_lite_app
from fly_mario_fly.lite.config import LiteConfig
from fly_mario_fly.lite.settings import canonicalize

SLACK = float(os.environ.get("FMF_PERF_SLACK", "1"))
SRC = str(Path(__file__).resolve().parents[1] / "src")
MB = 2**20

# Budgets for one full 1-1 run of the champion fly (about 2350 frames, a flag run).
WALL_S = 30 * SLACK          # one run with its video, measured ~12 s
RSS_MB = 350 * SLACK         # measured ~105 MB, one brain, no data, no pyarrow
VIDEO_MB = 2.5               # measured ~1.3 MB for a 39 s clip with the brain panel
OVERHEAD = 1.7 * SLACK       # drawing + encoding vs the same run with no video: measured ~1.3x
BUNDLE_MB = 60               # brains 41 MB + a few small files
HEAVY = ("pyarrow", "pandas", "cma", "httpx", "websockets")


@pytest.fixture(scope="module")
def data_root():
    if not os.environ.get("FLY_MARIO_FLY_DATA"):
        pytest.skip("FLY_MARIO_FLY_DATA not set")
    return Path(os.environ["FLY_MARIO_FLY_DATA"])


@pytest.fixture(scope="module")
def lite_bundle(data_root, tmp_path_factory):
    dest = tmp_path_factory.mktemp("lite_bundle")
    try:
        info = bundle.build(dest, data_root, ("1-1", "1-2"))
    except FileNotFoundError as e:
        pytest.skip(f"brains are not built in the data folder: {e}")
    return dest, info


def champion_request(max_frames=3600):
    from fly_mario_fly.runner import load_fly
    from fly_mario_fly.runner.config import FLIES
    from fly_mario_fly.api import schemas as S
    return S.RunRequestDTO(fly=V.fly_to_dto(load_fly(FLIES / "champion_e1s.yaml")), scene=S.SceneDTO(level_id="1-1", max_frames=max_frames))


SCRIPT = textwrap.dedent('''
    import json, sys, time
    from pathlib import Path
    bundle_dir, settings_json, out_mp4, keep = sys.argv[1:5]
    from fly_mario_fly.lite import engine
    from fly_mario_fly.lite.config import LiteConfig
    from fly_mario_fly.lite.settings import Settings
    from fly_mario_fly.runner import session
    cfg = LiteConfig(bundle_dir=Path(bundle_dir))
    engine.init_worker(bundle_dir, int(keep))
    t0 = time.perf_counter()
    out = engine.render(settings_json, out_mp4, out_mp4 + ".progress", cfg.worker_json())
    lite_s = time.perf_counter() - t0
    # the same run again with no drawing and no video: what the picture costs
    from fly_mario_fly.api import convert as V, schemas as S
    from fly_mario_fly.runner import Run, Options
    raw = json.loads(settings_json)
    st = Settings(fly=raw["fly"], dials=raw["dials"], level_id=raw["level"], modifiers=(), max_frames=raw["max_frames"])
    t0 = time.perf_counter()
    r = Run(V.with_dials(V.dto_to_fly(st.fly_dto()), st.dials), st.scene(cfg), Options())
    res = r.play(); r.close()
    plain_s = time.perf_counter() - t0
    # VmHWM is this process's own peak; ru_maxrss can carry the (large) test runner's peak over fork + exec, so prefer VmHWM
    rss = None
    try:
        rss = int([l for l in open("/proc/self/status") if l.startswith("VmHWM")][0].split()[1]) / 1024
    except OSError:
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 if sys.platform != "darwin" else 1024 * 1024)
        except ImportError:
            pass
    heavy = [m for m in %r if m in sys.modules]
    print("RESULT" + json.dumps({"hash": out["result"]["hash"], "plain_hash": res.hash, "outcome": out["result"]["outcome"],
          "frames": out["result"]["counts"]["frames"], "video_bytes": out["video_bytes"], "video_frames": out["video_frames"],
          "lite_s": lite_s, "plain_s": plain_s, "rss_mb": rss, "heavy": heavy, "brains_in_memory": len(session._BRAINS)}))
''' % (HEAVY,))


def run_lite_subprocess(bundle_dir, settings, tmp_path, keep=2):
    """One lite run in a fresh interpreter with NO data folder in its environment. Returns the measurements it printed."""
    env = {k: v for k, v in os.environ.items() if k != "FLY_MARIO_FLY_DATA"}
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-W", "ignore", "-c", SCRIPT, str(bundle_dir), settings.to_json(), str(tmp_path / "out.mp4"), str(keep)],
                       env=env, capture_output=True, text=True, timeout=600)
    wall = time.perf_counter() - t0
    assert p.returncode == 0, p.stderr[-2000:]
    line = next(x for x in p.stdout.splitlines() if x.startswith("RESULT"))
    out = json.loads(line[len("RESULT"):])
    out["process_s"] = wall
    return out


@pytest.fixture(scope="module")
def champion_run(lite_bundle, tmp_path_factory):
    dest, _ = lite_bundle
    st = canonicalize(champion_request(), LiteConfig(bundle_dir=dest, levels=("1-1", "1-2")))
    return st, run_lite_subprocess(dest, st, tmp_path_factory.mktemp("run"))


# ---- correctness: the same run as the full tool -------------------------------------------------------------------------
def test_lite_run_is_the_full_tools_run(champion_run, data_root):
    from fly_mario_fly.runner import Run, Options
    st, out = champion_run
    cfg = LiteConfig(levels=("1-1",))
    r = Run(V.with_dials(V.dto_to_fly(st.fly_dto()), st.dials), st.scene(cfg), Options())
    full = r.play()
    r.close()
    assert out["hash"] == full.hash == out["plain_hash"]
    assert out["outcome"] == full.outcome == "flag"


# ---- time ---------------------------------------------------------------------------------------------------------------
def test_a_full_run_is_fast_enough(champion_run):
    _, out = champion_run
    assert out["lite_s"] < WALL_S, f"{out['lite_s']:.1f} s for {out['frames']:.0f} frames (budget {WALL_S:.0f} s)"


def test_the_video_costs_little_on_top_of_the_run(champion_run):
    _, out = champion_run
    ratio = out["lite_s"] / out["plain_s"]
    assert ratio < OVERHEAD, f"with video {out['lite_s']:.1f} s, without {out['plain_s']:.1f} s ({ratio:.2f}x; budget {OVERHEAD:.2f}x)"


# ---- memory and space ---------------------------------------------------------------------------------------------------
def test_a_run_stays_inside_the_memory_budget(champion_run):
    _, out = champion_run
    if out["rss_mb"] is None:
        pytest.skip("no resource module on this platform")
    assert out["rss_mb"] < RSS_MB, f"peak {out['rss_mb']:.0f} MB (budget {RSS_MB:.0f} MB)"


def test_the_worker_does_not_load_the_data_stack(champion_run):
    _, out = champion_run
    assert out["heavy"] == [], f"imported {out['heavy']}: the lite worker should not need them"


def test_the_video_is_small(champion_run):
    _, out = champion_run
    assert out["video_bytes"] < VIDEO_MB * MB, f"{out['video_bytes'] / MB:.2f} MB"
    assert out["video_frames"] == pytest.approx(out["frames"] / 4, abs=2)       # 15 fps from 60


def test_the_bundle_is_small(lite_bundle):
    dest, info = lite_bundle
    assert len(list((dest / "panels").glob("*.npz"))) == len(list((dest / "brains").glob("*.npz")))     # one brain panel per brain
    assert info["bytes"] < BUNDLE_MB * MB, f"{info['bytes'] / MB:.1f} MB"


def test_brains_in_memory_are_capped(lite_bundle, tmp_path):
    """keep=1: a fly that needs a different brain replaces the loaded one instead of adding to it (the cap holds the memory down)."""
    dest, _ = lite_bundle
    st = canonicalize(request(attachments={"looming": ["goomba"]}, max_frames=300), LiteConfig(bundle_dir=dest))
    out = run_lite_subprocess(dest, st, tmp_path, keep=1)
    assert out["brains_in_memory"] <= 1


# ---- the whole server with the real engine -----------------------------------------------------------------------------
@pytest.fixture
def real_client(lite_bundle, tmp_path):
    dest, _ = lite_bundle
    cfg = LiteConfig(bundle_dir=dest, cache_dir=tmp_path / "cache", workers=1, queue_max=4, rate_per_minute=1000)
    with TestClient(create_lite_app(cfg)) as c:
        c.cfg = cfg
        yield c


def wait_done(client, run_id, t=120 * SLACK):
    end = time.time() + t
    while time.time() < end:
        r = client.get(f"/runs/{run_id}").json()
        if r["status"] in ("done", "failed"):
            return r
        time.sleep(0.2)
    raise AssertionError("run did not finish in time")


def short(max_frames):
    return champion_request(max_frames).model_dump(mode="json")


def test_server_end_to_end_then_cache_hit_is_instant(real_client):
    r = real_client.post("/runs", json=short(600))
    assert r.status_code == 202 and r.json()["cached"] is False
    run_id = r.json()["run_id"]
    done = wait_done(real_client, run_id)
    assert done["status"] == "done", done
    assert done["summary"]["result"]["counts"]["frames"] <= 600
    v = real_client.get(done["video_url"])
    assert v.status_code == 200 and v.content[4:8] == b"ftyp" and len(v.content) == done["summary"]["video_bytes"]
    t0 = time.perf_counter()
    again = real_client.post("/runs", json=short(600)).json()
    status = real_client.get(f"/runs/{run_id}").json()
    ms = (time.perf_counter() - t0) * 1000
    assert again["cached"] is True and again["run_id"] == run_id and status["status"] == "done"
    assert ms < 150 * SLACK, f"a cached run took {ms:.0f} ms to answer"


def test_the_cache_stays_inside_its_byte_limit(lite_bundle, tmp_path):
    dest, _ = lite_bundle
    limit = int(0.35 * MB)                                    # one 600-frame clip is ~0.2 MB: room for one, not three
    cfg = LiteConfig(bundle_dir=dest, cache_dir=tmp_path / "cache", cache_max_bytes=limit, workers=1, queue_max=4, rate_per_minute=1000)
    with TestClient(create_lite_app(cfg)) as c:
        ids = []
        for frames in (480, 540, 600):
            run_id = c.post("/runs", json=short(frames)).json()["run_id"]
            assert wait_done(c, run_id)["status"] == "done"
            ids.append(run_id)
            assert c.app.state.cache.size() <= limit
        assert c.app.state.cache.keys() == [ids[-1]]


def test_a_run_over_its_time_budget_fails_cleanly(lite_bundle, tmp_path):
    dest, _ = lite_bundle
    cfg = LiteConfig(bundle_dir=dest, cache_dir=tmp_path / "cache", workers=1, wall_budget_s=0.3, queue_max=4, rate_per_minute=1000)
    with TestClient(create_lite_app(cfg)) as c:
        run_id = c.post("/runs", json=short(3600)).json()["run_id"]
        done = wait_done(c, run_id)
        assert done["status"] == "failed" and "longer than" in done["error"]
        assert sorted(p.name for p in cfg.cache_dir.iterdir()) == []             # no half video, no progress file left behind
        assert c.get(f"/videos/{run_id}.mp4").status_code == 404
