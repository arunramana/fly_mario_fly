"""Part 7b: the diagnosis replay is a pure observer: it reproduces run_episode's own summary and leaves the env/motor unpatched."""
from dataclasses import replace
from pathlib import Path

from flyrun import diagnose7b, motor, part7, run as R

CFG = Path(__file__).resolve().parent.parent / "configs" / "part7.yaml"


def test_capture_matches_run_episode_and_unpatches(brain):
    cfg = part7.load_config(CFG)
    ep = cfg["episodes"]["holdout"][0]
    kn = replace(diagnose7b.r3_knobs(cfg), SENSOR_NOISE=float(ep["sigma"]))
    decide = motor.decide
    s, df = diagnose7b.capture(kn, ep, brain)
    s2, df2 = R.run_episode(kn, brain, noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150)
    assert (s["max_x"], s["end_reason"], s["cause"], s["frames"]) == (s2["max_x"], s2["end_reason"], s2["cause"], s2["frames"])
    assert df[["x", "a", "ttmn"]].equals(df2[["x", "a", "ttmn"]])
    assert motor.decide is decide and "step" not in vars(R._get_env())
    assert {"y", "a_left", "cool_left", "enemies"} <= set(df.columns) and (df.a_left >= 0).all()
