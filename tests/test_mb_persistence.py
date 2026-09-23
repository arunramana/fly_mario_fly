"""REFACTOR_PLAN.md phase 6, step 1: "verify KC->MBON weight persistence...
This has been on the open list since sprint 014 and never checked. It is
now a hard prerequisite, not a loose end: death is the only aversive event,
it happens once, and it is terminal -- there is no subsequent behaviour in
that episode for it to modify. Punishment learning exists only across
episodes. Without persistence the appetitive side will work and the
aversive side will be a silent no-op, and we would read that as a
plasticity-rule failure."

Two checks, both required:
  1. A save/np.load round trip of a real, plasticity-modified matrix is
     exactly lossless -- the mechanical half.
  2. A genuinely NEW Python process, not just a second in-process call,
     reloads a saved matrix and continues training IDENTICALLY to an
     uninterrupted in-process continuation -- the actual prerequisite,
     since a subtle bug (module-global state, a re-seeded RNG that should
     have stayed put) could pass check 1 while still breaking this one.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import run_steering
from bridge.full_policy import FullPolicy
from config.project_config import ProjectConfig

REPO_ROOT = Path(__file__).parent.parent

# Same scenario as tests/golden/'s own sigma0 baseline (deterministic,
# reaches death at frame 689) -- reused here rather than invented, so a
# death-triggered punishment update is guaranteed to actually fire.
SCENARIO = dict(level="1-1", max_frames=800, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_mb_weights_round_trip_exact(tmp_path):
    policy = FullPolicy(config=ProjectConfig(), level="1-1")
    policy.reset(seed=0)
    original = policy.W_kc_mbon.copy()

    policy.mb_elig[:] = 0.0
    policy.mb_elig[:10] = 1.0
    policy.on_step(0, SimpleNamespace(done=True), action=0)
    assert not np.array_equal(policy.W_kc_mbon, original), (
        "the punishment update itself is a no-op before persistence even "
        "enters the picture -- fix that first, a broken save/load round "
        "trip of an untouched matrix would prove nothing"
    )

    path = tmp_path / "mb_weights.npy"
    np.save(path, policy.W_kc_mbon)
    reloaded = np.load(path)
    assert np.array_equal(reloaded, policy.W_kc_mbon), (
        "np.save/np.load round trip is not exact -- persistence cannot "
        "work at all if the matrix itself doesn't survive a save/load"
    )


def test_training_continues_identically_across_a_process_restart(tmp_path):
    tel1, info1 = run_steering.main(out_mp4=str(tmp_path / "ep1.mp4"), mb_weights=None, **SCENARIO)
    w1 = info1["mb_weights"]
    assert info1["died_or_flagged"], (
        "episode 1 must reach death for the punishment side to fire at "
        "all -- if this assertion fails the scenario itself changed, not "
        "the thing being tested"
    )
    # A snapshot, not the live reference -- FullPolicy now copies a
    # passed-in mb_weights (phase 6 fix), but this test's whole point is
    # to catch that class of bug, so it doesn't trust that fix either.
    w1_snapshot = w1.copy()

    w1_path = tmp_path / "w1.npy"
    np.save(w1_path, w1)

    # Reference: continue training in THIS process, entirely in memory.
    tel2_ref, info2_ref = run_steering.main(out_mp4=str(tmp_path / "ep2_ref.mp4"),
                                             mb_weights=w1, **SCENARIO)
    w2_ref = info2_ref["mb_weights"]
    assert not np.array_equal(w1_snapshot, w2_ref), (
        "episode 2 produced no change in W_kc_mbon at all -- learning "
        "isn't happening in this scenario, independent of persistence; "
        "fix that before this test can say anything about persistence"
    )

    # The real check: a NEW Python process loads w1 from disk and
    # continues training, writing its own result back to disk (a
    # subprocess has no return value to hand back directly).
    w2_subprocess_path = tmp_path / "w2_subprocess.npy"
    ep2_sub_path = tmp_path / "ep2_sub.mp4"
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "import numpy as np\n"
        "import run_steering\n"
        f"w1 = np.load({str(w1_path)!r})\n"
        "tel, info = run_steering.main(\n"
        f"    out_mp4={str(ep2_sub_path)!r}, mb_weights=w1,\n"
        f"    level={SCENARIO['level']!r}, max_frames={SCENARIO['max_frames']!r},\n"
        f"    sigma={SCENARIO['sigma']!r}, seed={SCENARIO['seed']!r},\n"
        "    record_video=False, write_telemetry=False,\n"
        ")\n"
        f"np.save({str(w2_subprocess_path)!r}, info['mb_weights'])\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                             text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, (
        f"subprocess continuation crashed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    w2_subprocess = np.load(w2_subprocess_path)

    assert np.array_equal(w2_subprocess, w2_ref), (
        "a process restart changed the training outcome -- reloading a "
        "saved matrix from disk in a new process does NOT pick up where "
        "the last process left off. This is the failure mode phase 6's "
        "own prompt warned about: punishment learning would look like a "
        "silent no-op across any real (multi-process) training run."
    )
