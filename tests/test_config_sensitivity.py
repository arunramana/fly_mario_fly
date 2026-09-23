"""tool/PLAN.md C1: `run_steering.main(config=None)` must actually drive a
run from the config it's given, not silently build its own default and
discard the caller's. Two checks: changing a circuit scalar in a passed
config changes telemetry, and `config=None` still reproduces the exact
default behaviour goldens are frozen against.
"""
from __future__ import annotations

import dataclasses

import run_steering
from config.project_config import ProjectConfig

SCENARIO = dict(level="1-1", max_frames=200, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_changing_a_circuit_scalar_in_config_changes_telemetry(tmp_path):
    default_cfg = ProjectConfig()
    tel_default, _ = run_steering.main(out_mp4=str(tmp_path / "default.mp4"),
                                        config=default_cfg, **SCENARIO)

    loud_jump = dataclasses.replace(default_cfg.jump, g=default_cfg.jump.g * 3)
    loud_cfg = dataclasses.replace(default_cfg, jump=loud_jump)
    tel_loud, _ = run_steering.main(out_mp4=str(tmp_path / "loud.mp4"),
                                     config=loud_cfg, **SCENARIO)

    assert not tel_default["ttmn"].equals(tel_loud["ttmn"]), (
        "tripling jump.g in a passed-in config produced identical TTMn "
        "telemetry to the default -- the config isn't actually driving "
        "the run (C1's whole point)"
    )


def test_config_none_reproduces_default_behaviour_exactly(tmp_path):
    """config=None (the new argument's default) must be byte-for-byte the
    same as passing an explicit, unmodified ProjectConfig() -- proving the
    new code path is genuinely additive, not a second, subtly different
    way of doing what main() already did."""
    tel_implicit, info_implicit = run_steering.main(
        out_mp4=str(tmp_path / "implicit.mp4"), config=None, **SCENARIO)
    tel_explicit, info_explicit = run_steering.main(
        out_mp4=str(tmp_path / "explicit.mp4"), config=ProjectConfig(), **SCENARIO)

    assert tel_implicit.equals(tel_explicit)
    assert info_implicit["n_frames"] == info_explicit["n_frames"]
    assert info_implicit["died_or_flagged"] == info_explicit["died_or_flagged"]
