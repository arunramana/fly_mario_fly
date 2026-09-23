"""tool/PLAN.md C4: score/coins/time/flag from the gym `info` dict, into
the returned summary `info` -- not the telemetry CSV, which the fitness
tab's "points" control has nothing to read without this.
"""
from __future__ import annotations

import filecmp

import run_steering

SCENARIO = dict(level="1-1", max_frames=200, sigma=0.0, seed=0, record_video=False)


def test_summary_info_gains_score_coins_time_flag(tmp_path):
    tel, info = run_steering.main(out_mp4=str(tmp_path / "run.mp4"),
                                   telemetry_path=str(tmp_path / "run_telemetry.csv"),
                                   write_telemetry=True, **SCENARIO)

    for key in ("score", "coins", "time", "flag_get"):
        assert key in info, f"summary info is missing {key!r}"
    assert isinstance(info["score"], int)
    assert isinstance(info["coins"], int)
    assert isinstance(info["time"], int)
    assert isinstance(info["flag_get"], bool)


def test_csv_is_not_touched_by_the_new_keys(tmp_path):
    """The new summary keys must not add columns to the telemetry CSV --
    goldens are frozen against its exact current column set."""
    csv_a = tmp_path / "a_telemetry.csv"
    csv_b = tmp_path / "b_telemetry.csv"
    run_steering.main(out_mp4=str(tmp_path / "a.mp4"), telemetry_path=str(csv_a),
                       write_telemetry=True, **SCENARIO)
    run_steering.main(out_mp4=str(tmp_path / "b.mp4"), telemetry_path=str(csv_b),
                       write_telemetry=True, **SCENARIO)
    assert filecmp.cmp(csv_a, csv_b, shallow=False)
