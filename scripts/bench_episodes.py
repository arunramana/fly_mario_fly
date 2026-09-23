"""
bench_episodes.py -- SPEC_throughput.md: measure the actual episodes/minute
before and after making episodes cheap. No new circuits; this only changes
how fast the existing ones run.

Levers, in the order they actually mattered (measured, not assumed):
  1. Circuit-load memoization (bridge.full_policy._memo_load) -- ~6.8s of
     the ~7-8s a single episode used to cost was just re-reading the same
     6 cached circuits from disk every call. This alone is the single
     biggest win and needed no new infrastructure, just not throwing away
     work already done. Live copy is in FullPolicy; run_steering no longer
     owns a duplicate.
  2. Headless (record_video=False) -- already existed, just needs using.
  3. multiprocessing.Pool(8), OMP_NUM_THREADS=1 per worker (same pattern
     compare_controllers.py already established) -- each worker pays the
     ~6.8s circuit load ONCE (via the pool initializer) and reuses it for
     every episode that worker runs after.
  4. Frame skip (main()'s frame_skip param) -- included, reported
     separately, NOT recommended as a default: SPEC_throughput.md's own
     verification found its effect on a single deterministic trajectory is
     chaotic (1-1 got much worse, 1-2 got much better, 1-3 unaffected,
     across 3 tested values), not reliably "unchanged" the way frame_skip=1
     is by construction. It measurably helps raw throughput; it does not
     reliably preserve behaviour on any single seed.
  5. Savestates (main()'s savestate param, nes-py's own _backup/_restore)
     -- eliminates warm-up replay cost per episode. Reported as its own
     lever since it's orthogonal to the Pool/memoization win.

    .venv/Scripts/python.exe -m scripts.bench_episodes
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import multiprocessing as mp
import time

N_EPISODES = 24
MAX_FRAMES = 2500
N_WORKERS = 8


def _pool_worker_init():
    """Runs once per worker process -- pays the ~6.8s circuit-load cost a
    single time, so every episode after the first in this worker is warm."""
    import run_steering as rs
    rs.main(out_mp4="IGNORED", level="1-1", max_frames=2, record_video=False)


def _run_one_episode(args):
    level, frame_skip, use_savestate = args
    import run_steering as rs
    t0 = time.time()
    kwargs = dict(out_mp4="IGNORED", level=level, max_frames=MAX_FRAMES,
                  record_video=False, frame_skip=frame_skip)
    if use_savestate:
        env = getattr(_run_one_episode, "_env", None)
        if env is None or getattr(_run_one_episode, "_level", None) != level:
            env = rs.make_env(level)
            _run_one_episode._env = env
            _run_one_episode._level = level
        kwargs["savestate"] = {"env": env, "warmup_frames": 60}
    tel, info = rs.main(**kwargs)
    return time.time() - t0, info["n_frames"]


def measure_before():
    """Cold process, video on, frame_skip=1 -- the literal current usage
    pattern this whole project has been running all session."""
    import subprocess
    import sys
    code = (
        "import sys, time; sys.path.insert(0, '.'); import run_steering as rs; "
        "t0=time.time(); "
        "tel, info = rs.main(out_mp4='runs/_bench_tmp.mp4', level='1-1', "
        "max_frames=2500, record_video=True); "
        "print(f'BENCH_RESULT {time.time()-t0:.2f} {info[\"n_frames\"]}')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=".")
    line = [l for l in out.stdout.splitlines() if l.startswith("BENCH_RESULT")]
    if not line:
        print(out.stdout[-2000:], out.stderr[-2000:])
        raise RuntimeError("before-measurement subprocess produced no parseable output")
    _, dt, n_frames = line[0].split()
    return float(dt), int(n_frames)


def measure_after(frame_skip=1, use_savestate=False, n_episodes=N_EPISODES):
    tasks = [("1-1", frame_skip, use_savestate)] * n_episodes
    t0 = time.time()
    with mp.Pool(N_WORKERS, initializer=_pool_worker_init) as pool:
        results = pool.map(_run_one_episode, tasks)
    total_wall = time.time() - t0
    return total_wall, results


if __name__ == "__main__":
    import os as _os
    if _os.path.exists("runs/_bench_tmp.mp4"):
        _os.remove("runs/_bench_tmp.mp4")

    print("=== BEFORE: cold process, video on, frame_skip=1 (current usage as-is) ===")
    dt_before, n_frames_before = measure_before()
    eps_min_before = 60.0 / dt_before
    print(f"  1 episode: {dt_before:.2f}s ({n_frames_before} frames) -> {eps_min_before:.3f} episodes/minute")
    if _os.path.exists("runs/_bench_tmp.mp4"):
        _os.remove("runs/_bench_tmp.mp4")

    print(f"\n=== AFTER: memoized loads + headless + Pool({N_WORKERS}), frame_skip=1 (no chaotic-timing risk) ===")
    wall1, results1 = measure_after(frame_skip=1, use_savestate=False)
    eps_min1 = len(results1) / (wall1 / 60.0)
    print(f"  {len(results1)} episodes in {wall1:.2f}s -> {eps_min1:.2f} episodes/minute "
          f"({eps_min1/eps_min_before:.1f}x the before rate)")

    print(f"\n=== AFTER + frame_skip=4 (throughput lever; behaviour NOT verified stable, see writeup) ===")
    wall4, results4 = measure_after(frame_skip=4, use_savestate=False)
    eps_min4 = len(results4) / (wall4 / 60.0)
    print(f"  {len(results4)} episodes in {wall4:.2f}s -> {eps_min4:.2f} episodes/minute "
          f"({eps_min4/eps_min_before:.1f}x the before rate)")

    print(f"\n=== AFTER + savestate (skip 60-frame warm-up replay per episode) ===")
    wall_s, results_s = measure_after(frame_skip=1, use_savestate=True)
    eps_min_s = len(results_s) / (wall_s / 60.0)
    print(f"  {len(results_s)} episodes in {wall_s:.2f}s -> {eps_min_s:.2f} episodes/minute "
          f"({eps_min_s/eps_min_before:.1f}x the before rate)")
