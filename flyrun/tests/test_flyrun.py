from dataclasses import replace

import numpy as np
import pandas as pd

from flyrun.brain import REQUIRED
from flyrun.knobs import Knobs
from flyrun.run import run_episode
from .conftest import record

COLUMNS = ["frame", "x", "score", "theta", "dtheta", "tau", "ttmn", "dnp09", "steer",
           "buttons", "a", "right", "left"]
CLEAR_X = 340  # nb 09: "alive past the first Goomba"


def test_masks(brain):
    counts = brain.counts()
    record("type_counts", counts)
    for name, _, _ in REQUIRED:
        assert counts[name] > 0, f"{name} missing from W_steer"
    assert brain.W.shape[0] == brain.W.shape[1] == len(brain.bodies)


def test_silence(brain):
    k = replace(Knobs(), HOME_R=0.0)
    s, df = run_episode(k, brain, max_frames=600, enemy_input=False)
    record("silence", dict(s, a_presses=int(df["a"].sum())))
    assert s["max_x"] < 60
    assert df["a"].sum() == 0


def test_homing(brain):
    s, df = run_episode(Knobs(), brain, max_frames=600)
    record("homing", dict(s, right_frac=float(df["right"].mean())))
    assert s["max_x"] > 200
    assert df["right"].mean() > 0.5


def test_telemetry(brain):
    s, df = run_episode(Knobs(), brain, max_frames=300)
    for c in COLUMNS:
        assert c in df.columns, c
    assert not df[["x", "ttmn", "buttons"]].isna().any().any()
    record("telemetry", dict(columns=list(df.columns), rows=len(df)))
    for key in ("max_x", "score", "flag_get", "frames", "end_reason", "x_at_end"):
        assert key in s


def test_determinism(brain):
    k = Knobs()
    s1, d1 = run_episode(k, brain, noop_start=0, max_frames=300)
    s2, d2 = run_episode(k, brain, noop_start=0, max_frames=300)
    s3, d3 = run_episode(k, brain, noop_start=17, max_frames=300)
    n = min(len(d1), len(d3))
    differs = bool((d1["x"].to_numpy()[:n] != d3["x"].to_numpy()[:n]).any())
    record("determinism", dict(same_max_x=[s1["max_x"], s2["max_x"]],
                               noop0_max_x=s1["max_x"], noop17_max_x=s3["max_x"],
                               noop17_differs=differs))
    assert s1["max_x"] == s2["max_x"]
    assert d1["x"].tolist() == d2["x"].tolist()
    assert differs


def test_parity(brain):
    """Report only (no pass/fail on the numbers): nb 09 cleared knobs vs NOTES.md d~20-24, theta~37-44."""
    s, df = run_episode(Knobs(), brain, max_frames=400)
    first = df[df["a"] == 1].head(1)
    out = dict(first_A_frame=None, first_A_d=None, first_A_theta_deg=None, first_A_tau=None)
    if len(first):
        r = first.iloc[0]
        th = float(r["theta"])
        out = dict(first_A_frame=int(r["frame"]),
                   first_A_d=float(Knobs().W_ENEMY / (2 * np.tan(th / 2))),  # invert theta = 2 atan(w/2d)
                   first_A_theta_deg=float(np.degrees(th)), first_A_tau=float(r["tau"]))
    alive_past = bool(s["max_x"] >= CLEAR_X and s["end_reason"] != "died")
    out["goomba1_cleared"] = alive_past
    out["end_reason"] = s["end_reason"]
    record("parity", out)
    print("PARITY", out)
