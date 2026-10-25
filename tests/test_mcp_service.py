"""The MCP tools as plain functions: reading, adding plug-ins from fixed recipes, setting dials, and REFUSING rule-breaking requests."""
import importlib.util
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml

from fly_mario_fly import registry
from fly_mario_fly.mcp_server import codegen as cg
from fly_mario_fly.mcp_server import service as S
from fly_mario_fly.runner import load_fly

FLIES = Path(__file__).resolve().parents[1] / "configs" / "flies"


@pytest.fixture
def ws(tmp_path):
    flies = tmp_path / "flies"
    flies.mkdir()
    for n in ("blank", "looming_only"):
        shutil.copy(FLIES / f"{n}.yaml", flies / f"{n}.yaml")
    plugins = {"senses": tmp_path / "senses", "objects": tmp_path / "objects"}
    return S.Workspace(plugin_dirs=plugins, flies_dir=flies)


def files(ws):
    return sorted(p.name for d in ws.plugin_dirs.values() for p in d.glob("*.py")) if ws.plugin_dirs else []


def load(path):
    spec = importlib.util.spec_from_file_location("written_" + Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def refused_rules(res):
    assert res["ok"] is False and res["nothing_written"] is True
    return {r["rule"] for r in res["refused"]}


def sense(**kw):
    base = dict(name="warm_smell", label="Warm smell", effect="A warm thing smells good to the antenna on its side.", cue="angular_size",
                route="attraction", drives=["ORN_L", "ORN_R"], gain=100.0, split_by_side=True)
    return {**base, **kw}


# ---- reading --------------------------------------------------------------------------------------------------------------

def test_list_rules_has_every_rule_the_colour_rule_and_what_no_tool_can_do():
    r = S.list_rules()
    assert {x["id"] for x in r["rules"]} >= {"D1", "D2", "D3", "D4", "N1", "N2", "N3", "S1", "S2"}
    assert "teal" in r["colour_rule"] and "orange" in r["colour_rule"]
    assert any("weights" in c for c in r["tools_cannot"]) and any("fire neurons" in c for c in r["tools_cannot"])
    assert "The wiring is untouched; a few dials are evolved." in r["honesty"]


def test_list_plugins_labels_every_plugin_teal_or_orange():
    out = S.list_plugins()["plugins"]
    assert {p["kind"] for p in out} >= {"senses", "actions", "objects", "shapes", "scenes", "mechanisms"}
    assert all(p["colour"] == ("teal" if p["origin"] == "fly" else "orange") for p in out)
    assert {p["name"] for p in S.list_plugins("mechanisms")["plugins"]} == {"escape", "walking", "hearing", "attraction", "aversion"}
    assert all(p["colour"] == "teal" for p in S.list_plugins("mechanisms")["plugins"])
    assert {p["name"] for p in S.list_plugins("characters")["plugins"]} == {"buzzy_beetle", "red_koopa", "hammer_bro", "podoboo"}
    assert S.list_plugins("nonsense")["ok"] is False


def test_explain_plugin_gives_the_route_and_dials():
    e = S.explain_plugin("senses", "looming")
    assert e["declaration"]["colour"] == "orange" and e["declaration"]["route"]["colour"] == "teal"
    assert "DNp01" in e["declaration"]["route"]["wiring"] and "LPLC2_R" in e["declaration"]["drives"]
    assert all(d["colour"] == "orange" for d in e["dials"]) and e["source"].endswith("looming.py")
    assert S.explain_plugin("senses", "nope")["ok"] is False


# ---- add_sense ------------------------------------------------------------------------------------------------------------

def test_add_sense_writes_a_valid_plugin_labelled_orange_with_a_teal_route(ws):
    res = S.add_sense(**sense(), workspace=ws)
    assert res["ok"] and res["colour"] == "orange" and res["declaration"]["route"]["colour"] == "teal"
    assert files(ws) == ["warm_smell.py"] and Path(res["written"]).exists()
    mod = load(res["written"])
    assert mod.PLUGIN.name == "warm_smell" and mod.PLUGIN.feeds == ["attraction"] and mod.DECLARATION.drives == ("ORN_L", "ORN_R")
    assert [d["key"] for d in res["dials"]] == ["warm_smell.gain"] and res["dials"][0]["origin"] == "invented"


def test_a_written_sense_drives_only_the_antenna_on_the_objects_side(ws):
    from fly_mario_fly.contracts import Box, MarioState, ObjectInstance
    from fly_mario_fly.mario.facts import load_facts
    from fly_mario_fly.senses.kit.memory import SenseMemory
    mod = load(S.add_sense(**sense(), workspace=ws)["written"])
    m = MarioState(x=100.0, y=160.0, w=12.0, h=16.0, airborne=False, power="small", facing=1)
    mem = SenseMemory()
    mem.rng, mem.sigma, mem.world, mem.mods = np.random.default_rng(0), 0.0, [], {}
    knobs = {k.key: k.default for k in mod.PLUGIN.knobs}
    right = mod.PLUGIN.cue([ObjectInstance("x", 0, Box(160, 160, 16, 16), "ahead")], m, load_facts("1-1"), knobs, mem)
    left = mod.PLUGIN.cue([ObjectInstance("x", 0, Box(20, 160, 16, 16), "behind")], m, load_facts("1-1"), knobs, mem)
    assert right.inputs["ORN_R"] > 0 and right.inputs["ORN_L"] == 0
    assert left.inputs["ORN_L"] > 0 and left.inputs["ORN_R"] == 0


@pytest.mark.parametrize("cue,extra", [("proximity", {}), ("constant", {"route": "walking", "drives": ["LC10a_R"], "split_by_side": False})])
def test_other_cue_recipes_are_accepted(ws, cue, extra):
    assert S.add_sense(**sense(cue=cue, **extra), workspace=ws)["ok"]


def test_dry_run_checks_but_writes_nothing(ws):
    res = S.add_sense(**sense(), dry_run=True, workspace=ws)
    assert res["ok"] and res["dry_run"] and "would_write" in res and files(ws) == []


def test_a_sense_that_would_fire_a_motor_or_descending_neuron_is_refused(ws):
    for group in ("DNp01", "TTMn"):
        res = S.add_sense(**sense(name="bad_one", route="escape", drives=[group], cue="constant"), workspace=ws)
        assert "R-SENSE-ROUTE" in refused_rules(res)
        assert "cannot be driven" in " ".join(r["message"] for r in res["refused"])
    assert files(ws) == []


def test_a_sense_must_ride_a_real_circuit_and_its_input_groups(ws):
    assert "R-FLY-ROUTE" in refused_rules(S.add_sense(**sense(route="no_such_circuit"), workspace=ws))
    assert "R-SENSE-ROUTE" in refused_rules(S.add_sense(**sense(route="escape"), workspace=ws))        # ORN groups are not escape inputs
    assert files(ws) == []


@pytest.mark.parametrize("bad", [
    {"name": "Bad Name!"}, {"name": "x"}, {"name": "looming"}, {"cue": "teleport"}, {"colour": "pink"}, {"gain": -1}, {"gain": float("nan")},
    {"gain": True}, {"gain": 1e9}, {"label": "two\nlines"}, {"label": "x"}, {"effect": ""}, {"drives": []}, {"drives": ["a b"]},
    {"split_by_side": "yes"}, {"range_px": 1.0},
], ids=lambda d: next(iter(d)) + "=" + str(next(iter(d.values()))).replace("\n", "\\n")[:12])
def test_malformed_requests_are_refused_without_writing(ws, bad):
    assert refused_rules(S.add_sense(**sense(**bad), workspace=ws))
    assert files(ws) == []


def test_nothing_is_ever_overwritten(ws):
    assert S.add_sense(**sense(), workspace=ws)["ok"]
    assert S.add_sense(**sense(), workspace=ws)["ok"] is False
    assert files(ws) == ["warm_smell.py"]


def test_hostile_text_cannot_leave_its_literal(ws, tmp_path):
    nasty = 'a\'b"c""" + __import__("os").system("touch PWNED") + """'
    res = S.add_sense(**sense(label="Warm " + nasty[:30], what="Invented: " + nasty + " (real wiring onward)", effect="e" + nasty), workspace=ws)
    assert res["ok"], res
    mod = load(res["written"])
    assert mod.PLUGIN.label.startswith("Warm a'b") and nasty in mod.DECLARATION.what
    assert not (Path.cwd() / "PWNED").exists() and not (tmp_path / "PWNED").exists()
    assert S.add_sense(**sense(name="newline", label="x\n__import__('os')"), workspace=ws)["ok"] is False


def test_the_recipe_lists_match_the_template_module():
    from fly_mario_fly.senses.kit import templates
    assert cg.CUES == templates.CUES and set(cg.COLOURS) == set(templates.COLOURS)


# ---- add_character / add_object -------------------------------------------------------------------------------------------

def test_add_character_finds_a_creature_by_its_type_byte(ws):
    from fly_mario_fly.mario import ram as R
    from fly_mario_fly.mario.env import MarioEnv
    res = S.add_character("blobby", "Blobby", "A made-up creature.", [0x15], [16, 16], workspace=ws)
    assert res["ok"] and res["kind"] == "character" and res["colour"] == "orange"
    plugin = load(res["written"]).PLUGIN
    env = MarioEnv()
    try:
        env.reset("1-1", noop=3)
        r = env.facts["ram"]
        env.poke(r["enemy_active"] + 1, 1), env.poke(r["enemy_type"] + 1, 0x15), env.poke(r["enemy_state"] + 1, 0)
        env.poke(r["enemy_page"] + 1, 0), env.poke(r["enemy_x"] + 1, 200), env.poke(r["enemy_y"] + 1, 184)
        found = plugin.find(env.ram, env.facts)
        assert [(o.type, o.id, o.box.x, o.box.w, o.box.h) for o in found] == [("blobby", 1, 200, 16, 16)]
        plugin.remove(env)
        assert plugin.find(env.ram, env.facts) == []
    finally:
        env.close()


def test_add_character_refuses_a_taken_type_byte_and_bad_numbers(ws):
    assert "R-INPUT" in refused_rules(S.add_character("clone", "Clone", "x" * 5, [6], [16, 16], workspace=ws))       # 6 = goomba
    assert refused_rules(S.add_character("big", "Big one", "x" * 5, [0x15], [16, 900], workspace=ws))
    assert refused_rules(S.add_character("bytes", "Bytes", "x" * 5, [300], [16, 16], workspace=ws))
    assert refused_rules(S.add_character("empty", "Empty", "x" * 5, [], [16, 16], workspace=ws))
    assert files(ws) == []


def test_add_object_finds_terrain_by_tile_id(ws):
    from fly_mario_fly.mario import ram as R
    from fly_mario_fly.mario.env import MarioEnv
    res = S.add_object("slab", "Slab", "A made-up wall.", [200], workspace=ws)
    assert res["ok"] and res["colour"] == "orange"
    plugin = load(res["written"]).PLUGIN
    env = MarioEnv()
    try:
        env.reset("1-1", noop=3)
        facts, g = env.facts, env.facts["grid"]
        wx = R.visible_columns(env.ram, facts)[8]
        for row in (g["stand_row"], g["stand_row"] - 1):
            addr = facts["ram"]["tile_buffer"] + g["page_bytes"] * ((wx // 256) % 2) + 16 * row + (wx % 256) // g["tile"]
            env.poke(addr, 200)
        found = plugin.find(env.ram, facts)
        assert len(found) == 1 and found[0].type == "slab" and found[0].box.h == 32
    finally:
        env.close()


def test_add_object_refuses_tile_ids_another_object_owns(ws):
    res = S.add_object("fake_pipe", "Fake pipe", "x" * 5, [18], workspace=ws)
    assert "R-INPUT" in refused_rules(res) and "pipe" in res["refused"][0]["message"]
    assert refused_rules(S.add_object("zero", "Zero", "x" * 5, [0], workspace=ws))
    assert files(ws) == []


# ---- flies: create_fly, add_cue, set_dial ------------------------------------------------------------------------------------

def test_create_fly_copies_and_never_overwrites(ws):
    res = S.create_fly("mine", "looming_only", workspace=ws)
    assert res["ok"] and (ws.flies() / "mine.yaml").exists() and "looming" in res["senses"]
    assert S.create_fly("mine", "blank", workspace=ws)["ok"] is False
    assert S.create_fly("../evil", "blank", workspace=ws)["ok"] is False and not (ws.flies().parent / "evil.yaml").exists()
    assert S.create_fly("x", "no_such_fly", workspace=ws)["ok"] is False


def test_add_cue_attaches_a_sense_to_objects(ws):
    S.create_fly("mine", "blank", workspace=ws)
    res = S.add_cue("mine", "looming", ["goomba", "pipe"], workspace=ws)
    assert res["ok"] and res["cue"]["colour"] == "orange" and "DNp01" in res["cue"]["route"]
    fly = load_fly(ws.flies() / "mine.yaml")
    assert fly.attachments["looming"] == frozenset({"goomba", "pipe"})
    S.add_cue("mine", "looming", ["koopa"], workspace=ws)
    assert load_fly(ws.flies() / "mine.yaml").attachments["looming"] == frozenset({"goomba", "pipe", "koopa"})
    assert S.add_cue("mine", "home", [], workspace=ws)["ok"] and "home" in load_fly(ws.flies() / "mine.yaml").whole_fly


@pytest.mark.parametrize("args", [("looming", ["no_such_object"]), ("no_such_sense", ["goomba"]), ("home", ["goomba"])])
def test_add_cue_refuses_unknown_things(ws, args):
    S.create_fly("mine", "blank", workspace=ws)
    before = (ws.flies() / "mine.yaml").read_text()
    assert S.add_cue("mine", *args, workspace=ws)["ok"] is False
    assert (ws.flies() / "mine.yaml").read_text() == before


def test_set_dial_changes_one_dial_and_reports_old_and_new(ws):
    S.create_fly("mine", "looming_only", workspace=ws)                        # a fly this server made may be edited in place
    res = S.set_dial("mine", "jump.ttmn_thresh", 0.12, workspace=ws)
    assert res["ok"] and res["dial"]["colour"] == "orange" and res["dial"]["new"] == 0.12 and res["dial"]["old"] != 0.12
    assert load_fly(ws.flies() / "mine.yaml").knobs["jump.ttmn_thresh"] == 0.12


def test_set_dial_save_as_leaves_the_original_alone(ws):
    before = (ws.flies() / "looming_only.yaml").read_text()
    res = S.set_dial("looming_only", "jump.ttmn_thresh", 0.12, save_as="tweaked", workspace=ws)
    assert res["ok"] and (ws.flies() / "tweaked.yaml").exists() and (ws.flies() / "looming_only.yaml").read_text() == before
    assert S.set_dial("looming_only", "jump.ttmn_thresh", 0.12, save_as="tweaked", workspace=ws)["ok"] is False      # no silent overwrite


def test_set_dial_dry_run_writes_nothing(ws):
    S.create_fly("mine", "looming_only", workspace=ws)
    before = (ws.flies() / "mine.yaml").read_text()
    assert S.set_dial("mine", "jump.ttmn_thresh", 0.12, dry_run=True, workspace=ws)["ok"]
    assert (ws.flies() / "mine.yaml").read_text() == before


@pytest.mark.parametrize("key", ["W", "weights", "brain.W", "LPLC2_R", "neurons.DNp01", "jump.nothing", "../x", ""])
def test_only_dials_can_be_set_never_weights_or_neurons(ws, key):
    res = S.set_dial("looming_only", key, 1.0, save_as="probe", workspace=ws)
    assert res["ok"] is False and res["nothing_written"] and "protected" not in res["refused"][0]["message"]
    assert not (ws.flies() / "probe.yaml").exists()
    assert (ws.flies() / "looming_only.yaml").read_text() == (FLIES / "looming_only.yaml").read_text()


@pytest.mark.parametrize("value", [99.0, -1.0, float("nan"), float("inf"), "0.1", None, True])
def test_a_dial_value_must_be_inside_its_range(ws, value):
    res = S.set_dial("looming_only", "jump.ttmn_thresh", value, save_as="probe", workspace=ws)
    assert res["ok"] is False and not (ws.flies() / "probe.yaml").exists()


def test_fly_names_cannot_be_paths(ws):
    for name in ("../looming_only", "a/b", "C:\\x", "x.yaml"):
        assert S.set_dial(name, "jump.ttmn_thresh", 0.1, workspace=ws)["ok"] is False


# ---- run_fly -----------------------------------------------------------------------------------------------------------------

def test_run_fly_without_the_brain_cache_says_so_and_downloads_nothing(ws, monkeypatch):
    monkeypatch.delenv("FLY_MARIO_FLY_DATA", raising=False)
    res = S.run_fly("looming_only", workspace=ws)
    assert res["ok"] is False and "never downloads" in res["error"]


def test_run_fly_checks_its_arguments(ws):
    for kw in ({"seed": -1}, {"sigma": 2.0}, {"max_frames": 10**7}, {"noop": "x"}, {"level": "x" * 50}):
        assert S.run_fly("looming_only", workspace=ws, **kw)["ok"] is False
    assert S.run_fly("no_such_fly", workspace=ws)["ok"] is False


needs_data = pytest.mark.skipif(not os.environ.get("FLY_MARIO_FLY_DATA"), reason="FLY_MARIO_FLY_DATA not set")


@needs_data
def test_run_fly_summarises_a_headless_run_reproducibly(ws):
    res = S.run_fly("looming_only", seed=101, noop=3, workspace=ws)
    assert res["ok"] and res["outcome"] == "flag" and res["hash"] == "261f48b6cb2f" and res["max_x"] == 3161.0
    assert {s["colour"] for s in res["senses"]} == {"orange"} and "goomba" in res["objects_seen"]
    assert S.run_fly("looming_only", seed=101, noop=3, workspace=ws)["hash"] == res["hash"]


@needs_data
def test_run_fly_reports_a_rule_violation_instead_of_crashing(ws, monkeypatch):
    from dataclasses import replace

    from fly_mario_fly.rules.lookup import _modules
    mod = _modules("senses")["looming"]
    monkeypatch.setattr(mod, "DECLARATION", replace(mod.DECLARATION, drives=("LC4_L",)))
    res = S.run_fly("looming_only", seed=1, noop=3, max_frames=900, workspace=ws)
    assert res["ok"] is False and "looming" in res["rule_violation"]


def test_a_sense_written_while_the_server_runs_is_found_at_once(tmp_path, monkeypatch):
    """The runner looks up each sense's declaration; a new file must not be hidden by import or lookup caches."""
    from fly_mario_fly.rules import lookup
    pkg = tmp_path / "tmp_senses_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(registry.KINDS, "senses", "tmp_senses_pkg")
    lookup._modules.cache_clear()
    try:
        assert registry.list_plugins("senses") == {}
        res = S.add_sense(**sense(), workspace=S.Workspace(plugin_dirs={"senses": pkg}, flies_dir=tmp_path / "flies"))
        assert res["ok"], res
        assert set(registry.list_plugins("senses")) == {"warm_smell"}
        assert lookup.declaration_of("senses", "warm_smell").drives == ("ORN_L", "ORN_R")
    finally:
        lookup._modules.cache_clear()


# ---- the committed reference flies are never edited in place ----------------------------------------------------------------

COMMITTED = sorted(p.stem for p in FLIES.glob("*.yaml") if p.stem in ("blank", "looming_only", "champion_e1s"))


@pytest.mark.parametrize("name", COMMITTED)
def test_committed_flies_are_never_edited_in_place(ws, name):
    repo_before = (FLIES / f"{name}.yaml").read_bytes()
    tmp_before = {p.name: p.read_bytes() for p in ws.flies().glob("*.yaml")}
    for res in (S.set_dial(name, "jump.ttmn_thresh", 0.12, workspace=ws),
                S.add_cue(name, "looming", ["goomba"], workspace=ws),
                S.set_dial(name, "jump.ttmn_thresh", 0.12, dry_run=True, workspace=ws)):
        assert refused_rules(res) == {"R-INPUT"} and "save_as" in res["refused"][0]["message"]
    assert (FLIES / f"{name}.yaml").read_bytes() == repo_before
    assert {p.name: p.read_bytes() for p in ws.flies().glob("*.yaml")} == tmp_before


def test_a_committed_fly_can_be_edited_as_a_copy(ws):
    before = (FLIES / "champion_e1s.yaml").read_bytes()
    res = S.set_dial("champion_e1s", "jump.ttmn_thresh", 0.12, save_as="champ_copy", workspace=ws)
    assert res["ok"] and load_fly(ws.flies() / "champ_copy.yaml").knobs["jump.ttmn_thresh"] == 0.12
    assert S.add_cue("champion_e1s", "looming", ["koopa"], save_as="champ_copy2", workspace=ws)["ok"]
    assert (FLIES / "champion_e1s.yaml").read_bytes() == before


def test_a_fly_the_server_made_is_editable_in_place_but_a_hand_made_lookalike_is_not(ws):
    S.create_fly("mine", "blank", workspace=ws)
    assert S.set_dial("mine", "jump.ttmn_thresh", 0.12, workspace=ws)["ok"]
    assert S.set_dial("mine", "jump.ttmn_thresh", 0.13, workspace=ws)["ok"]                      # still the server's own
    path = ws.flies() / "handmade.yaml"
    path.write_text((ws.flies() / "blank.yaml").read_text().replace("name: blank", "name: handmade"))
    assert refused_rules(S.set_dial("handmade", "jump.ttmn_thresh", 0.12, workspace=ws)) == {"R-INPUT"}
