"""R2: saved moments (the store, auto and before-death moments), resume, tries_from, the CLI's test scenes, and the
level object list joined with what saved runs saw.

Moments, runs and levels.json go to a temp folder (record.runs_dir / levels.cache_path are redirected); the MaleCNS data and
the brain caches are only read, from the real $FLY_MARIO_DATA."""
import json
import os
from dataclasses import replace

import numpy as np
import pytest
import yaml

from fly_mario.contracts import Scene
from fly_mario.runner import (Options, Run, delete_moment, describe_change, get_moment, level_catalogue, level_info,
                              level_objects, list_moments, load_fly, moment_info, rename_moment, save_moment, save_run,
                              tries_from)
from fly_mario.runner import levels as L
from fly_mario.runner import record
from fly_mario.runner.__main__ import main, parse_scene_modifier

pytestmark = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(record, "runs_dir", lambda: tmp_path / "runs")
    monkeypatch.setattr(L, "cache_path", lambda: tmp_path / "levels.json")
    return tmp_path


def play(run_id, level="1-1", fly="champion_e1s", opts=Options(moment_every_s=1.0), **scene):
    run = Run(load_fly(fly) if isinstance(fly, str) else fly, Scene(level, noop=3, sigma=0.05, seed=7, **scene), opts,
              run_id=run_id, moments=True)
    return run, run.play()


# ---- the store ------------------------------------------------------------------------------------------------
def test_a_manual_moment_is_listed_loaded_renamed_and_deleted():
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=3, max_frames=100), run_id="m1", moments=True)
    for _ in range(40):
        run.step()
    info = save_moment(run, name="before the pipe")
    assert info.id == "m1@40" and info.kind == "manual" and not info.auto and info.frame == 40
    m = get_moment(info.id)
    assert m.frame == 40 and m.scene == run.scene and m.fly == run.fly and isinstance(m.emulator_state, bytes)
    assert set(m.brain_state) == {int(b) for b in run.brain.body_ids} and m.rng_state is not None
    assert [i.id for i in list_moments("m1")] == ["m1@40"] and moment_info(info.id).name == "before the pipe"
    assert rename_moment(info.id, "pipe 1").name == "pipe 1" and list_moments("m1")[0].name == "pipe 1"
    with pytest.raises(ValueError):
        save_moment(run, frame=7)                                    # not a frame the run still has a snapshot of
    delete_moment(info.id)
    assert list_moments("m1") == []
    with pytest.raises(KeyError):
        get_moment(info.id)


def test_auto_moments_rotate_but_manual_and_death_moments_stay():
    run = Run(load_fly("champion_e1s"), Scene("1-2", noop=3, sigma=0.05, seed=7), Options(moment_every_s=0.5, keep_auto=3),
              run_id="rot", moments=True)
    run.start()
    for _ in range(100):
        run.step()
    manual = save_moment(run, name="mine")
    seen_events = []
    while not run.finished:
        seen_events += run.step().moments
    kinds = [i.kind for i in list_moments("rot")]
    assert run.outcome == "died" and kinds.count("auto") == 3 and kinds.count("manual") == 1 and kinds.count("death") == 1
    assert manual.id in {i.id for i in list_moments("rot")}
    assert {e.kind for e in seen_events} == {"auto", "death"}       # the per-frame callback carried the events


def test_a_death_on_1_2_saves_the_moment_three_seconds_before():
    run, res = play("d12", "1-2")
    assert res.outcome == "died"
    death = [i for i in list_moments("d12") if i.kind == "death"]
    assert len(death) == 1 and death[0].name == "3 s before death"
    assert death[0].frame <= res.counts["frames"] - 180 and res.counts["frames"] - death[0].frame < 180 + 60
    assert "koopa" in death[0].on_screen or "goomba" in death[0].on_screen or death[0].on_screen
    assert death[0].id in res.moments


def test_the_callback_receives_moment_events():
    got = []
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=3, max_frames=260), Options(moment_every_s=1.0), run_id="ev", moments=True)
    run.play(on_frame=lambda rec: got.extend(rec.moments))
    assert [i.frame for i in got] == [60, 120, 180, 240]


def test_no_moments_unless_asked():
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=3, max_frames=150), run_id="quiet")
    run.play()
    assert list_moments("quiet") == []


# ---- resume ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("level,frames", [("1-1", 400), ("1-2", 400)])
def test_resuming_with_the_same_fly_reproduces_the_original_from_that_frame(level, frames):
    full, res = play("orig", level, max_frames=frames)
    mid = next(i.id for i in list_moments("orig") if i.kind == "auto" and i.frame == 120)
    resumed = Run(load_fly("champion_e1s"), from_moment=mid, run_id="again", moments=True)
    res2 = resumed.play()
    assert res2.hash == res.hash and res2.outcome == res.outcome and res2.max_x == res.max_x
    assert [r["x"] for r in resumed.rows] == [r["x"] for r in full.rows[120:]]
    assert resumed.rows[0]["frame"] == full.rows[120]["frame"] and res2.parent_moment == mid


def test_resuming_with_a_stronger_sour_smell_keeps_the_old_neurons_rates():
    fly = load_fly("champion_e1s")
    _, _ = play("base", "1-1", max_frames=300)
    mid = next(i.id for i in list_moments("base") if i.frame == 180 and i.kind == "auto")
    m = get_moment(mid)
    stronger = replace(fly, name="sour_stronger", knobs={**fly.knobs, "sour_smell.gain": fly.knobs["sour_smell.gain"] * 2})
    run = Run(stronger, from_moment=mid, run_id="sour2")
    run.start()
    ids = run.brain.body_ids
    rest = np.array([m.brain_state.get(int(b), 0.0) for b in ids])
    assert np.array_equal(run.h, rest) and run.h.any()                          # shared neurons carry their rates over
    res = run.play(on_frame=None)
    assert res.parent_moment == mid and res.counts["frames"] > 0


def test_resuming_with_a_different_brain_drops_removed_neurons_and_starts_new_ones_at_rest():
    _, _ = play("big", "1-1", max_frames=200)
    mid = next(i.id for i in list_moments("big") if i.frame == 120 and i.kind == "auto")
    m = get_moment(mid)
    small = Run(load_fly("looming_only"), from_moment=mid, run_id="small")      # no smell: fewer neurons
    small.start()
    assert small.brain.n < len(m.brain_state)
    assert np.array_equal(small.h, np.array([m.brain_state.get(int(b), 0.0) for b in small.brain.body_ids]))
    _, _ = play("lo", "1-1", fly="looming_only", max_frames=200)
    mid2 = next(i.id for i in list_moments("lo") if i.frame == 120 and i.kind == "auto")
    big = Run(load_fly("champion_e1s"), from_moment=mid2, run_id="big2")
    big.start()
    new = ~np.isin(big.brain.body_ids, list(get_moment(mid2).brain_state))
    assert new.any() and not big.h[new].any()                                   # new neurons at rest
    assert big.h[~new].any()


def test_senses_that_were_not_on_before_start_with_fresh_memory():
    _, _ = play("mem", "1-1", fly="looming_only", max_frames=200)
    mid = next(i.id for i in list_moments("mem") if i.frame == 120 and i.kind == "auto")
    run = Run(load_fly("champion_e1s"), from_moment=mid, run_id="mem2")
    run.start()
    old = get_moment(mid).sense_memory["memory"]
    assert "looming" in old and dict(run.memory["looming"]) == old["looming"]
    assert "sour_smell" not in old and dict(run.memory["sour_smell"]) == {}


def test_resume_must_stay_on_the_moments_level():
    _, _ = play("lvl", "1-1", max_frames=150)
    with pytest.raises(ValueError, match="1-1"):
        Run(load_fly("champion_e1s"), Scene("1-2"), from_moment=list_moments("lvl")[0].id)


def test_tries_from_lists_runs_resumed_from_a_moment_with_the_change_in_words():
    fly = load_fly("champion_e1s")
    _, _ = play("par", "1-1", max_frames=200)
    mid = next(i.id for i in list_moments("par") if i.frame == 120 and i.kind == "auto")
    for rid, f in (("t_same", fly), ("t_sour", replace(fly, knobs={**fly.knobs, "sour_smell.gain": fly.knobs["sour_smell.gain"] * 2}))):
        run = Run(f, from_moment=mid, run_id=rid)
        save_run(run, run.play())
    tries = {t.run_id: t for t in tries_from(mid)}
    assert set(tries) == {"t_same", "t_sour"} and tries["t_same"].change == ""
    assert tries["t_sour"].change == "Sourness: toward strong" and tries["t_sour"].outcome in ("flag", "died", "stuck", "timeout")
    assert json.loads((record.runs_dir() / "t_sour" / "summary.json").read_text())["parent_moment"] == mid


def test_describe_change_in_words():
    fly = load_fly("champion_e1s")
    assert describe_change(fly, fly) == ""
    quiet = replace(fly, attachments={k: v for k, v in fly.attachments.items() if k != "sour_smell"},
                    actions=fly.actions - {"back_up"}, knobs={**fly.knobs, "hearing.gain": fly.knobs["hearing.gain"] / 2})
    text = describe_change(fly, quiet)
    assert "off" in text and "action back_up off" in text and "toward" in text
    assert not any(ch.isdigit() for ch in text)


# ---- test scenes in the CLI -----------------------------------------------------------------------------------
def test_scene_arguments_parse():
    assert parse_scene_modifier("keep_only:pit") == ("keep_only", {"types": ["pit"]})
    assert parse_scene_modifier("keep_only:pit,pipe") == ("keep_only", {"types": ["pit", "pipe"]})
    assert parse_scene_modifier("no_enemies") == ("no_enemies", {})
    with pytest.raises(SystemExit):
        parse_scene_modifier("keep_only")


def test_cli_runs_a_pits_only_scene_then_resumes_from_a_moment(capsys):
    assert main(["run", "champion_e1s", "--noop", "3", "--max-frames", "200", "--scene", "keep_only:pit",
                 "--run-id", "cli1", "--moment-every", "1"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["frames"] == 200 and out["moments"] == 3
    scene = yaml.safe_load((record.runs_dir() / "cli1" / "config.yaml").read_text())["scene"]
    assert scene["modifiers"] == [["keep_only", {"types": ["pit"]}]]
    assert main(["run", "-", "--from-moment", "cli1@120a", "--max-frames", "200", "--run-id", "cli2"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["from_moment"] == "cli1@120a" and out["frames"] == 200                  # frames count from the start of the episode
    assert main(["moments", "cli1"]) == 0 and "cli1@120a" in capsys.readouterr().out


# ---- level objects: the db for the stages, the scan + what runs saw for the other envs ------------------------------
def test_level_objects_come_from_the_db_and_runs_add_to_the_other_envs():
    assert "koopa" in level_info("1-2").objects and "koopa" in level_objects("1-2")          # known without any run or scan
    (record.runs_dir().parent / "levels.json").write_text(json.dumps({"version": L.CACHE_VERSION, "levels": {
        "full": {"width": 323, "flag_x": None, "partial": True, "stop": "cap", "objects": ["brick", "goomba"]}}}))
    assert "koopa" not in level_info("full").objects
    (record.runs_dir() / "seen1").mkdir(parents=True)
    (record.runs_dir() / "seen1" / "summary.json").write_text(json.dumps(
        {"level": "full", "outcome": "died", "max_x": 900, "objects_seen": ["koopa"]}), encoding="utf-8")
    assert "koopa" in level_info("full").objects and "koopa" in level_objects("full")
    cat = {c.id: c for c in level_catalogue()}
    assert "koopa" in cat["full"].objects and cat["random"].objects is None and cat["1-3"].objects
