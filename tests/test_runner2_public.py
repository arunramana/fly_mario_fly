"""R1: what the runner exposes for api/ and render/ -- per-frame objects and scroll, the level catalogue, brain display data."""
import json
import os

import numpy as np
import pytest

from fly_mario.contracts import ObjectInstance, Scene
from fly_mario.mario.env import level_ids
from fly_mario.runner import (BrainDisplay, LevelInfo, LevelStatus, Run, brain_display, level_catalogue, level_info, level_statuses,
                              load_fly, screen_scroll)
from fly_mario.runner import levels as L

needs_data = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")


# ---- per-frame objects and scroll ---------------------------------------------------------------------------
def test_screen_scroll_is_page_times_256_plus_x():
    facts = {"ram": {"screen_page": 1, "screen_x": 2}}
    ram = np.zeros(8, dtype=np.uint8)
    ram[1], ram[2] = 3, 40
    assert screen_scroll(ram, facts) == 3 * 256 + 40


@needs_data
def test_a_frame_record_carries_the_objects_found_and_the_scroll():
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=3, max_frames=400))
    run.start()
    recs = []
    while not run.finished:
        recs.append(run.step())
    assert len(recs) == 400
    seen = {o.type for r in recs for o in r.objects}
    assert {"goomba", "pipe"} <= seen                                  # 1-1's first 400 frames show both
    r = next(r for r in recs if r.found.get("goomba"))
    g = r.found["goomba"][0]
    assert isinstance(g, ObjectInstance) and g.type == "goomba" and g.box.w > 0 and isinstance(g.id, int)
    assert r.objects == [o for objs in r.found.values() for o in objs]
    assert all(isinstance(r.scroll_x, int) for r in recs)
    for a, b in zip(recs, recs[1:]):                                   # the offset after a frame is the next frame's offset
        assert a.scroll_x_after == b.scroll_x
    assert recs[-1].scroll_x > recs[0].scroll_x == 0                   # the screen scrolled as Mario walked
    assert any(0 <= o.box.x - r.scroll_x < 256 for r in recs for o in r.objects if o.type == "goomba")    # level px -> screen px


# ---- level catalogue ------------------------------------------------------------------------------------------
def _summary(folder, name, level, outcome, max_x):
    d = folder / name
    d.mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps({"level": level, "outcome": outcome, "max_x": max_x}), encoding="utf-8")


def test_status_from_saved_runs(tmp_path):
    _summary(tmp_path, "a", "1-1", "flag", 3000)
    _summary(tmp_path, "b", "1-1", "died", 900)
    _summary(tmp_path, "c", "1-2", "died", 1840.0)
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "summary.json").write_text("{not json", encoding="utf-8")
    st = level_statuses(tmp_path)
    assert st["1-1"] == LevelStatus(2, 1, 3000.0, "won 1/2")
    assert st["1-2"] == LevelStatus(1, 0, 1840.0, "best x 1840")
    assert "1-3" not in st and LevelStatus().text == "not tried"
    assert level_statuses(tmp_path / "nowhere") == {}


def test_catalogue_is_immediate_stages_come_from_the_db_and_the_other_envs_from_the_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "cache_path", lambda: tmp_path / "levels.json")
    monkeypatch.setattr(L.record, "runs_dir", lambda: tmp_path / "runs")
    monkeypatch.setattr(L, "MarioEnv", lambda *a, **k: pytest.fail("the catalogue must not touch the emulator"))
    (tmp_path / "levels.json").write_text(json.dumps({"version": L.CACHE_VERSION, "levels": {
        "1-1": {"width": 1, "flag_x": 1, "partial": True, "stop": "cap", "objects": ["koopa"]},       # ignored: 1-1 is in the db
        "full": {"width": 3161, "flag_x": 3161, "partial": False, "stop": "flag", "objects": ["goomba", "pit"]},
        "lost_levels": {"width": 900, "flag_x": None, "partial": True, "stop": "cap", "objects": ["brick"]}}}), encoding="utf-8")
    _summary(tmp_path / "runs", "r", "2-1", "flag", 2500)
    cat = {c.id: c for c in level_catalogue()}
    assert list(cat) == level_ids() and len(cat) == 35 and all(isinstance(c, LevelInfo) for c in cat.values())
    a = cat["1-1"]                                        # exact from the ROM, whatever the scan cache or the runs say
    assert a.source == "rom" and a.scanned and not a.partial and a.stop == "rom" and a.width == a.flag_x == 3161
    assert {"goomba", "koopa", "pipe", "pit", "qblock", "brick", "step", "mushroom"} <= set(a.objects)
    assert "piranha" not in a.objects and a.time_limit == 400 and a.contents["power-up"] >= 1
    assert all(c.source == "rom" and c.scanned and c.objects and c.width for k, c in cat.items() if k in level_ids()[:32])
    b, c, r = cat["full"], cat["lost_levels"], cat["random"]                      # not in the db: the old scan semantics
    assert b.source == "scan" and b.scanned and not b.partial and b.objects == ("goomba", "pit") and b.width == b.flag_x == 3161
    assert c.scanned and c.partial and c.stop == "cap" and c.objects == ("brick",) and c.flag_x is None
    assert not r.scanned and r.objects is None and r.width is None and r.kind == "mixed"
    assert cat["2-1"].status.text == "won 1/1" and level_info("1-3").objects is not None
    assert cat["2-2"].kind == "water" and cat["1-4"].kind == "castle" and cat["1-2"].kind == "underground"


def test_catalogue_with_no_cache_file_only_the_non_db_envs_are_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "cache_path", lambda: tmp_path / "levels.json")
    monkeypatch.setattr(L.record, "runs_dir", lambda: tmp_path / "runs")
    cat = {c.id: c for c in level_catalogue()}
    assert all(c.scanned and c.objects for k, c in cat.items() if k in level_ids()[:32])
    assert all(not cat[k].scanned and cat[k].objects is None for k in ("full", "random", "lost_levels"))


def test_scan_caches_and_marks_a_capped_scan_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "cache_path", lambda: tmp_path / "levels.json")
    monkeypatch.setattr(L.record, "runs_dir", lambda: tmp_path / "runs")
    monkeypatch.setattr(L, "config", lambda: {**L.yaml.safe_load(L.CONFIG.read_text(encoding="utf-8")),
                                              "scan": {"every": 2, "max_frames": 60, "max_seconds": 60}})
    e = L.scan_level("full")                              # the whole-game env is not in the level db: it keeps the scan
    assert e["partial"] and e["stop"] == "cap" and e["flag_x"] is None and e["width"] > 40
    assert level_info("full").partial and L.level_objects("full") == tuple(e["objects"])      # cached: no second scan


@needs_data
def test_kinds_in_the_yaml_match_the_area_type_in_ram():
    from fly_mario.mario.env import MarioEnv
    cfg, env = L.config(), MarioEnv()
    names = {0: "water", 1: "overground", 2: "underground", 3: "castle"}
    for lv in level_ids()[:32]:
        env.reset(lv)
        assert cfg["kinds"][lv] == names[int(env.ram[0x074E])], lv
    assert set(cfg["kinds"]) == set(level_ids())


@needs_data
def test_a_real_scan_of_1_1_reports_what_it_saw_and_why_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "cache_path", lambda: tmp_path / "levels.json")
    one = L.scan_level("1-1")                         # the simple driver dies at the pit near x=2470: a partial result
    assert one["stop"] in ("flag", "died", "cap") and one["partial"] == (one["flag_x"] is None) and one["width"] > 2000
    assert {"goomba", "pipe", "pit", "qblock"} <= set(one["objects"])


def test_precompute_scans_only_what_the_db_lacks(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "cache_path", lambda: tmp_path / "levels.json")
    monkeypatch.setattr(L.record, "runs_dir", lambda: tmp_path / "runs")
    monkeypatch.setattr(L, "MarioEnv", lambda *a, **k: pytest.fail("1-1 and 1-2 are in the db: nothing to scan"))
    L.precompute()
    assert not (tmp_path / "levels.json").exists()
    cat = {c.id: c for c in level_catalogue()}
    assert cat["1-1"].scanned and cat["1-1"].objects and cat["1-2"].scanned


# ---- brain display data --------------------------------------------------------------------------------------
@needs_data
def test_brain_display_matches_the_brain_and_groups_yaml():
    from fly_mario.fly import groups as G
    from fly_mario.runner import get_brain, brain_spec
    fly = load_fly("champion_e1s")
    d = brain_display(fly)
    brain = get_brain(brain_spec(fly))
    assert isinstance(d, BrainDisplay) and d.n_neurons == brain.n and d.all_xyz.shape == (141781, 3)
    table = G.load_groups()
    assert list(d.groups) == [n for n in table if n in brain.masks]                  # groups.yaml order
    assert [g.index for g in d.groups.values()] == sorted(g.index for g in d.groups.values())
    for name, g in d.groups.items():
        assert g.count == brain.counts()[name] == len(g.xyz) and g.role == table[name].role and g.colour == table[name].colour
        assert np.array_equal(g.body_ids, brain.body_ids[brain.masks[name]])
        assert not np.isnan(g.xyz).any(), name                                       # every circuit neuron is placed
    assert d.groups["LC4_L"].rgb == (57, 135, 229)
    assert sum(g.count for g in d.groups.values()) + len(d.other_xyz) == brain.n     # groups + relays = the whole brain
    assert {"JO", "ORN_L", "ORN_R"} <= set(d.placed_by_terminal) and "LC4_L" not in d.placed_by_terminal


@needs_data
def test_terminals_sit_in_the_brain_not_the_nerve_cord():
    from fly_mario.runner.display import BRAIN_Z_MAX
    d = brain_display(load_fly("champion_e1s"))
    xyz = d.groups["JO"].xyz
    assert (xyz[:, 2] < BRAIN_Z_MAX).all()
    assert np.array_equal(xyz, brain_display(load_fly("champion_e1s")).groups["JO"].xyz)          # cached: stable
