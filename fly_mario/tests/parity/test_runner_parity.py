"""Parity: the new runner plays the E1s champion exactly like the old tool.

The 10 old HOLDOUT episodes (noop 3/11/25/33/41 x sigma 0/0.05, seeds 101..110) are played once by the old code
(flyrun.run.run_episode with the E1s genome on the 907-neuron sour brain) and once by fly_mario with
configs/flies/champion_e1s.yaml in legacy mode. Required: the same outcome, and the same x after every frame and
the same buttons on every frame. Only tests/parity may import the old code; it is deleted at cleanup.
"""
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]                       # worktree root, where the old `flyrun` package lives
sys.path.insert(0, str(REPO_ROOT))

from fly_mario.contracts import Scene                     # noqa: E402
from fly_mario.runner import Options, Run, load_fly       # noqa: E402

pytestmark = [pytest.mark.parity_old, pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")]

HOLDOUT = [dict(noop=n, seed=100 + i + 1, sigma=sg) for sg in (0.0, 0.05) for i, n in enumerate((3, 11, 25, 33, 41))]
NAMES = {frozenset(): "NOOP", frozenset({"right"}): "R", frozenset({"right", "A"}): "R+A",
         frozenset({"left"}): "L", frozenset({"left", "A"}): "L+A"}


def _old_cache() -> Path:
    env = os.environ.get("FLY_MARIO_OLD_CACHE")
    for c in ([Path(env)] if env else []) + [p / "tutorials" / "_cache" for p in HERE.parents]:
        if (c / "W_steer_jo_orn_sour.npy").exists():
            return c
    pytest.skip("old tutorials/_cache not found (set FLY_MARIO_OLD_CACHE)")


@pytest.fixture(scope="module")
def old():
    import json
    cache = _old_cache()
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet"
    try:
        from flyrun import e1s_genome as G
        from flyrun.brain import load_brain
        from flyrun.run import run_episode
        brain = load_brain(cache)
    finally:
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    values = json.load(open(REPO_ROOT / "flyrun" / "runs" / "E1s_progress.json"))["best"]["values"]
    knobs, enemy_input = G.knobs_for(values)

    def play(ep):
        return run_episode(replace(knobs, SENSOR_NOISE=ep["sigma"]), brain, noop_start=ep["noop"], episode_seed=ep["seed"],
                           stuck_frames=150, enemy_input=enemy_input)
    return play


def test_champion_yaml_holds_the_exact_e1s_values():
    import json
    values = json.load(open(REPO_ROOT / "flyrun" / "runs" / "E1s_progress.json"))["best"]["values"]
    k = load_fly("champion_e1s").knobs
    ours = {"HOME_R": "home.drive", "HUM_GAIN": "hearing.gain", "SMELL_GAIN": "sweet_smell.gain", "SOUR_GAIN": "sour_smell.gain",
            "TTMN_THRESH": "jump.ttmn_thresh", "RELEASE_THRESH": "jump.release_thresh", "STEER_THRESH": "steer.thresh",
            "MDN_THRESH": "back_up.mdn_thresh"}
    assert {v: values[o] for o, v in ours.items()} == k


@pytest.mark.parametrize("ep", HOLDOUT, ids=lambda e: f"noop{e['noop']}-sigma{e['sigma']}")
def test_champion_matches_old_episode(old, ep):
    summary, df = old(ep)
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=ep["noop"], sigma=ep["sigma"], seed=ep["seed"], max_frames=3000, stuck_frames=150),
              Options(legacy=True))
    result = run.play()
    new = pd.DataFrame(run.rows)
    new["name"] = [NAMES[frozenset(b.split("+")) - {"NOOP"}] for b in new.buttons]
    old_rows = df.iloc[ep["noop"]:].reset_index(drop=True)
    assert result.outcome == summary["end_reason"]
    assert (result.max_x, result.score) == (summary["max_x"], summary["score"])
    assert len(new) == len(old_rows), (len(new), len(old_rows))
    assert new.x.tolist() == old_rows.x.tolist(), "x per frame differs"
    assert new.name.tolist() == old_rows.buttons.tolist(), "buttons per frame differ"
    assert result.outcome == "flag"
