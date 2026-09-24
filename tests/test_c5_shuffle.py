"""tool/PLAN.md C5: `FullPolicy(shuffle_seed=None)` -- the shuffled-
connectome control CLAUDE.md invariant 6 says must ship with a feature,
not be added after.
"""
from __future__ import annotations

import run_steering

SCENARIO = dict(level="1-1", max_frames=300, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_shuffled_run_differs_from_real(tmp_path):
    tel_real, _ = run_steering.main(out_mp4=str(tmp_path / "real.mp4"), **SCENARIO)
    tel_shuf, _ = run_steering.main(out_mp4=str(tmp_path / "shuf.mp4"), shuffle_seed=1, **SCENARIO)
    assert not tel_real["ttmn"].equals(tel_shuf["ttmn"]), (
        "shuffle_seed=1 produced identical TTMn telemetry to the real "
        "connectome -- the shuffle isn't reaching the circuit"
    )


def test_shuffle_is_deterministic_and_default_is_unaffected(tmp_path):
    tel_a, _ = run_steering.main(out_mp4=str(tmp_path / "a.mp4"), shuffle_seed=7, **SCENARIO)
    tel_b, _ = run_steering.main(out_mp4=str(tmp_path / "b.mp4"), shuffle_seed=7, **SCENARIO)
    assert tel_a.equals(tel_b), "the same shuffle_seed produced different telemetry across two runs"

    tel_default, _ = run_steering.main(out_mp4=str(tmp_path / "default.mp4"), **SCENARIO)
    tel_explicit_none, _ = run_steering.main(out_mp4=str(tmp_path / "none.mp4"),
                                              shuffle_seed=None, **SCENARIO)
    assert tel_default.equals(tel_explicit_none), (
        "shuffle_seed=None (explicit) differs from leaving it out -- the new "
        "argument isn't purely additive"
    )
