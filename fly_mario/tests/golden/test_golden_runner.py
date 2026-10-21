"""Golden: the E1s champion plays the 10 HOLDOUT episodes (noop 3/11/25/33/41 x sigma 0/0.05, seeds 101..110) exactly like the old
tool did: same outcome, max_x and score, the same x after every frame and the same buttons on every frame (frozen by
tools/freeze_golden.py). configs/flies/champion_e1s.yaml in legacy mode, on the 907-neuron sour brain. Needs $FLY_MARIO_DATA."""
import os

import pytest

from fly_mario.contracts import Scene
from fly_mario.runner import Options, Run, load_fly
from golden_data import expand, load

pytestmark = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")
NAMES = {frozenset(): "NOOP", frozenset({"right"}): "R", frozenset({"right", "A"}): "R+A",
         frozenset({"left"}): "L", frozenset({"left", "A"}): "L+A"}
OURS = {"HOME_R": "home.drive", "HUM_GAIN": "hearing.gain", "SMELL_GAIN": "sweet_smell.gain", "SOUR_GAIN": "sour_smell.gain",
        "TTMN_THRESH": "jump.ttmn_thresh", "RELEASE_THRESH": "jump.release_thresh", "STEER_THRESH": "steer.thresh",
        "MDN_THRESH": "back_up.mdn_thresh"}
EPISODES = load("runner.json.gz")["episodes"]


def test_champion_yaml_holds_the_exact_e1s_values(golden):
    values = golden("runner.json.gz")["e1s_values"]
    assert {v: values[o] for o, v in OURS.items()} == load_fly("champion_e1s").knobs


@pytest.mark.parametrize("ep", EPISODES, ids=lambda e: f"noop{e['noop']}-sigma{e['sigma']}")
def test_champion_matches_the_frozen_old_episode(ep):
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=ep["noop"], sigma=ep["sigma"], seed=ep["seed"], max_frames=3000, stuck_frames=150),
              Options(legacy=True))
    result = run.play()
    names = [NAMES[frozenset(r["buttons"].split("+")) - {"NOOP"}] for r in run.rows]
    assert result.outcome == ep["outcome"] == "flag"
    assert (result.max_x, result.score) == (ep["max_x"], ep["score"])
    assert len(run.rows) == ep["n"], (len(run.rows), ep["n"])
    assert [r["x"] for r in run.rows] == ep["x"], "x per frame differs"
    assert names == expand(ep["buttons"]), "buttons per frame differ"
