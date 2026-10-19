"""A real (short) run through the emulator: the frame loop, the stuck rule, recording, reproducibility, resuming."""
import csv
import json
import os

import numpy as np
import pytest
import yaml

from fly_mario.contracts import Scene
from fly_mario.runner import Options, Run, fly_from_dict, fly_to_dict, load_fly, save_run
from fly_mario.runner import record
from fly_mario.runner.__main__ import main

pytestmark = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")


def play(fly="champion_e1s", legacy=False, **scene):
    run = Run(load_fly(fly), Scene("1-1", **scene), Options(legacy=legacy))
    return run, run.play()


def test_a_short_run_walks_right_and_logs_every_frame():
    run, res = play(noop=3, max_frames=60)
    assert res.outcome == "timeout" and res.counts["frames"] == 60 and len(run.rows) == 60 == len(run.rates["TTMn"])
    assert run.rows[0]["frame"] == 3 and run.rows[-1]["frame"] == 62            # frame numbers include the idle frames
    assert run.rows[-1]["x"] > run.rows[0]["x"]
    assert {"looming.angle", "looming.headroom", "home.home", "mod.headroom", "buttons", "byte"} <= set(run.rows[0])
    assert len(run.replay) == 63                                                  # 3 idle frames + 60 played


def test_the_fly_takes_over_only_after_the_idle_frames():
    run, _ = play(noop=10, max_frames=5)
    assert run.rows[0]["frame"] == 10 and run.replay[:10] == [0] * 10


def test_stuck_counts_only_after_the_first_move_unless_legacy():
    """A fly that never moves: the new rule never calls it stuck (it times out); the old rule counted from frame 0."""
    run, res = play("blank", noop=5, max_frames=80, stuck_frames=30)
    assert res.outcome == "timeout" and res.counts["frames"] == 80
    run, res = play("blank", legacy=True, noop=5, max_frames=80, stuck_frames=30)
    assert res.outcome == "stuck" and 5 + res.counts["frames"] == 31             # frame 30 counted from the very first frame


def test_legacy_max_frames_counts_the_idle_frames():
    _, res = play("blank", legacy=True, noop=5, max_frames=20, stuck_frames=1000)
    assert res.outcome == "timeout" and 5 + res.counts["frames"] == 20


def test_legacy_drops_a_bare_a():
    """The old tool had no A-alone combination; the new rule presses A on its own."""
    from fly_mario.runner.session import legacy_buttons
    assert legacy_buttons(frozenset({"A"})) == frozenset()
    assert legacy_buttons(frozenset({"right", "A"})) == {"right", "A"}
    assert legacy_buttons(frozenset({"left"})) == {"left"}


def test_same_seed_same_run_different_seed_different_run():
    a = play(noop=3, sigma=0.05, seed=1, max_frames=400)[1].hash
    assert a == play(noop=3, sigma=0.05, seed=1, max_frames=400)[1].hash
    assert a != play(noop=3, sigma=0.05, seed=2, max_frames=400)[1].hash
    assert play(noop=3, sigma=0.0, seed=1, max_frames=400)[1].hash == play(noop=3, sigma=0.0, seed=9, max_frames=400)[1].hash


def test_recording_writes_everything(tmp_path):
    run, res = play(noop=3, max_frames=40, sigma=0.05, seed=4)
    folder = save_run(run, res, tmp_path / "r1")
    assert {p.name for p in folder.iterdir()} == {"config.yaml", "frames.csv", "rates.npz", "replay.npz", "summary.json"}
    rows = list(csv.DictReader(open(folder / "frames.csv", encoding="utf-8")))
    assert len(rows) == 40 and "looming.angle" in rows[0] and "sour_smell.sourness" in rows[0]
    rates = np.load(folder / "rates.npz")
    assert rates["TTMn"].shape == (40,) and "MDN" in rates.files
    assert np.load(folder / "replay.npz")["buttons"].shape == (43,)
    summary = json.load(open(folder / "summary.json"))
    assert summary["outcome"] == "timeout" and summary["hash"] == res.hash and summary["seed"] == 4
    cfg = yaml.safe_load(open(folder / "config.yaml", encoding="utf-8"))
    assert fly_from_dict(cfg["fly"]) == load_fly("champion_e1s") and cfg["scene"]["sigma"] == 0.05


def test_ram_can_be_recorded_on_request(tmp_path):
    run = Run(load_fly("champion_e1s"), Scene("1-1", max_frames=5), Options(record_ram=True))
    folder = save_run(run, run.play(), tmp_path / "r2")
    assert np.load(folder / "replay.npz")["ram"].shape == (5, 2048)


def test_a_saved_moment_resumes_exactly():
    scene = Scene("1-1", noop=3, sigma=0.05, seed=7, max_frames=250)
    full = Run(load_fly("champion_e1s"), scene)
    moment = None
    for i in range(250):
        full.step()
        if i == 149:
            moment = full.snapshot("halfway")
    assert moment.frame == 150 and moment.id.endswith("@150")
    resumed = Run(load_fly("champion_e1s"), scene)
    resumed.restore(moment)
    for _ in range(100):
        resumed.step()
    assert [r["x"] for r in resumed.rows] == [r["x"] for r in full.rows[150:]]
    assert [r["buttons"] for r in resumed.rows] == [r["buttons"] for r in full.rows[150:]]
    assert resumed.rates["TTMn"] == full.rates["TTMn"][150:]


def test_scene_modifiers_apply():
    run = Run(load_fly("champion_e1s"), Scene("1-1", modifiers=(("no_enemies", {}),), max_frames=3))
    run.start()
    from fly_mario.mario import ram as R
    assert R.active_slots(run.env.ram, run.env.facts) == []


def test_cli_prints_a_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(record, "runs_dir", lambda: tmp_path)
    assert main(["run", "champion_e1s", "--level", "1-1", "--noop", "2", "--sigma", "0", "--seed", "3",
                 "--max-frames", "30", "--run-id", "cli_test"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["id"] == "cli_test" and out["frames"] == 30 and (tmp_path / "cli_test" / "summary.json").exists()
