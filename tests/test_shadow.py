# What this file does, in plain English:
# Tests shadow mode (a human plays, the fly only watches). It checks by reading the
# source that only the human's buttons are ever sent to the emulator and that the
# brain code cannot write to the game, that a scripted human run plays out
# bit-for-bit identically (game memory and screen, every frame) whether the fly
# is watching or not, that the log has all its columns, and that the analysis
# gives the known answers on a made-up log. It does not open the keyboard window.
"""docs/SPEC_shadow.md. Static (AST) non-influence checks in the style of tests/test_import_guard.py; the behavioural test needs
nes-py and the cached network and skips with a reason otherwise."""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import brain
from brain import builder, shadow, shadow_analysis as SA
from brain.calibration import CALIBRATION_FILE
from mario.actions.actions import action_from_buttons

BRAIN_DIR = Path(brain.__file__).parent
needs_net = pytest.mark.skipif(not builder.default_path().exists(), reason="network not built (python -m brain.builder)")
needs_cal = pytest.mark.skipif(not CALIBRATION_FILE.exists(), reason="brain/calibration.json missing")
# the files on the brain's path from observation to buttons: none may touch the emulator
POLICY_PATH_FILES = ("policy.py", "mechanisms.py", "motor_map.py", "brain.py", "perception.py", "obstacles.py", "calibration.py")


def _tree(name: str) -> ast.AST:
    return ast.parse((BRAIN_DIR / name).read_text(encoding="utf-8"), filename=name)


def _is_ram_store(target: ast.AST) -> bool:
    if isinstance(target, ast.Subscript):
        v = target.value
        return (isinstance(v, ast.Name) and v.id == "ram") or (isinstance(v, ast.Attribute) and v.attr == "ram")
    return False


# ---- (a) static non-influence -------------------------------------------------------------------------------------
def test_only_the_human_action_reaches_env_step_and_the_policy_result_is_dropped():
    tree = _tree("shadow.py")
    steps = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "step"
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "env"]
    assert len(steps) == 1, "exactly one env.step call"
    call = steps[0]
    assert not call.keywords and len(call.args) == 1 and isinstance(call.args[0], ast.Name) and call.args[0].id == "human_action"
    # human_action is built from the human's buttons only
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "human_action" for t in n.targets)]
    assert len(assigns) == 1 and ast.dump(assigns[0].value).count("_human_action") == 1 and "policy" not in ast.unparse(assigns[0])
    # policy.act(...) is only ever a bare statement: its returned action goes nowhere
    acts = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "act"]
    bare = [n.value for n in ast.walk(tree) if isinstance(n, ast.Expr)]
    assert acts and all(a in bare for a in acts), "policy.act()'s return value must be dropped"
    # the harness writes no RAM and presses nothing else
    for n in ast.walk(tree):
        targets = n.targets if isinstance(n, ast.Assign) else ([n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign)) else [])
        assert not any(_is_ram_store(t) for t in targets), "shadow mode must not write RAM"
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"act_on", "write_ram", "set_ram", "_write", "send_action"}


def test_the_brain_path_has_no_emulator_import_no_env_calls_and_no_ram_writes():
    for name in POLICY_PATH_FILES:
        tree = _tree(name)
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module:
                assert not n.module.startswith(("mario.emulator", "nes_py", "gym")), f"{name} imports the emulator: {n.module}"
            if isinstance(n, ast.Import):
                assert not any(a.name.startswith(("nes_py", "gym", "mario.emulator")) for a in n.names), name
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
                assert not (n.func.value.id in ("env", "emulator") and n.func.attr in ("step", "reset")), f"{name} drives the emulator"
            targets = n.targets if isinstance(n, ast.Assign) else ([n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign)) else [])
            assert not any(_is_ram_store(t) for t in targets), f"{name} writes RAM"
    imports = {n.module for n in ast.walk(_tree("shadow.py")) if isinstance(n, ast.ImportFrom) and n.module}
    assert "mario.emulator.env" in imports and not any(m and "write" in m for m in imports)


# ---- (b)+(c) behavioural: the brain makes no difference to the game ----------------------------------------------------
def _scripted_actions(n: int = 250) -> np.ndarray:
    out = []
    for t in range(n):
        out.append(action_from_buttons(right=True, b=(t % 40 < 25), a=(t % 50 in range(10, 22)) or (t % 90 in range(60, 63))))
    return np.asarray(out, dtype=np.uint8)


@pytest.fixture(scope="module")
def played(tmp_path_factory):
    pytest.importorskip("gym_super_mario_bros", reason="needs nes-py / gym-super-mario-bros")
    if not builder.default_path().exists() or not CALIBRATION_FILE.exists():
        pytest.skip("network or calibration not built")
    net = builder.load_or_build()
    actions = _scripted_actions()
    d = tmp_path_factory.mktemp("shadow")
    kw = dict(seed=9400, hash_states=True, network=net, rest_frames=90, rest_settle=60)
    with_p = shadow.run_shadow(shadow.ReplaySource(actions), "clean", out_csv=d / "001_clean.csv", with_policy=True, **kw)
    without = shadow.run_shadow(shadow.ReplaySource(actions), "clean", out_csv=None, with_policy=False, **kw)
    return actions, with_p, without, d


@needs_net
@needs_cal
def test_replayed_human_run_is_bit_identical_with_and_without_the_fly(played):
    actions, with_p, without, _ = played
    assert with_p.frames == without.frames and with_p.end_reason == without.end_reason and with_p.frames >= 200
    assert len(with_p.state_hashes) == len(without.state_hashes) == with_p.frames
    assert with_p.state_hashes == without.state_hashes          # RAM + screen identical on every frame
    assert (with_p.human_actions == actions[:with_p.frames]).all() and (without.human_actions == with_p.human_actions).all()


@needs_net
@needs_cal
def test_the_fly_really_ran_and_disagreed_with_the_human_somewhere(played):
    _, _, _, d = played
    df = pd.read_csv(d / "001_clean.csv")
    assert df["theta"].notna().all() and df["gf_l_hz"].notna().all() and df["muscle_drive"].notna().all()
    disagree = ((df["fly_a"] != df["human_a"]) | (df["fly_right"] != df["human_right"]) | (df["fly_b"] != df["human_b"])).any()
    assert disagree, "the fly's would-be buttons differ from the human's, yet the game followed the human (so the test is not vacuous)"


@needs_net
@needs_cal
def test_telemetry_columns_rows_label_and_sidecar_files(played):
    actions, with_p, _, d = played
    df = pd.read_csv(d / "001_clean.csv")
    n = with_p.frames
    assert list(df.columns) == shadow.COLUMNS and len(df) == n
    assert (df["label"] == "clean").all() and (df["frame"] == np.arange(1, n + 1)).all()
    for col in ("mario_x", "mario_y", "mario_size", "airborne", "human_a", "human_right", "human_start", "fly_a", "theta", "dtheta", "d_px",
                "obst_theta", "obst_d_px", "enemy_dx", "gf_l_hz", "gf_r_hz", "ttmn_hz", "dnp09_hz", "dna01_hz", "dna02_hz", "mdn_hz",
                "gf_mem", "gf_mem_l", "gf_mem_r", "gf_spike", "muscle_drive", "muscle_over", "lc10a_l", "lc10a_r", "landmark_on",
                "goombas_on_screen", "flag_get_after", "ttmn_rest_max"):
        assert col in df.columns
    assert (df["landmark_on"] == 1).all() and df["lc10a_r"].max() > 0           # B11 senses: landmark on the right
    assert (np.load(d / "001_clean_actions.npy") == actions[:n]).all()
    meta = (d / "001_clean_meta.json").read_text(encoding="utf-8")
    assert '"ttmn_rest_max"' in meta and "the fly controls nothing" in meta
    assert df["human_a"].sum() == int(np.sum([shadow.buttons_of(int(a))["A"] for a in actions[:n]]))
    with pytest.raises(FileExistsError):
        shadow.run_shadow(shadow.ReplaySource(actions[:3]), "clean", out_csv=d / "001_clean.csv", with_policy=False)


def test_shadow_runs_with_the_b11_senses_and_no_retinotopic_option():
    import dataclasses
    from brain.settings import SenseSettings, settings_for
    assert shadow.SHADOW_EXPERIMENT == "B11"
    assert settings_for("B11") == dataclasses.replace(SenseSettings.user_default(), obstacle_expansion=True)
    assert "retinotopic" not in (BRAIN_DIR / "settings.py").read_text(encoding="utf-8").lower()


def test_keyboard_source_maps_x_to_a_and_z_to_b_without_opening_a_window():
    src = shadow.KeyboardSource(fps=1e9)
    src._keys = {"left": 1, "right": 2, "up": 3, "down": 4, "a": 5, "b": 6, "start": 7}

    class FakeViewer:
        is_escape_pressed = False
        pressed_keys = (2, 5)
    src._viewer = FakeViewer()
    got = src.poll()
    assert got["right"] and got["a"] and not got["b"] and not got["left"] and not got["select"]
    FakeViewer.is_escape_pressed = True
    assert src.poll() is None


# ---- (d) analysis on a synthetic CSV with known answers --------------------------------------------------------------
A_THR, WALK_THR, REST = 0.1323, 0.0169, 0.01


def _synthetic(spikes) -> pd.DataFrame:
    n = 200
    df = pd.DataFrame({c: np.zeros(n) for c in shadow.COLUMNS})
    df["label"] = "clean"
    df["frame"] = np.arange(1, n + 1)
    df["run"] = 0
    df["mario_x"] = np.arange(n) * 4.0
    df["ttmn_rest_max"] = REST
    for lo, hi in ((50, 55), (120, 123), (180, 181)):          # human A held: presses (rising edges) at 50, 120, 180; 9 A frames
        df.loc[lo:hi - 1, "human_a"] = 1
    df.loc[52:54, "muscle_drive"] = 0.2                        # >= A_THR on 3 of the 5 frames of press 1
    df.loc[120:121, "muscle_drive"] = 0.2                      # and 2 of the 3 of press 2
    df.loc[51:54, "ttmn_hz"] = 0.02
    df.loc[120:122, "ttmn_hz"] = 0.02                          # above rest on 7 of the 9 A frames
    df.loc[10:19, "human_right"] = 1
    df.loc[60:69, "human_right"] = 1                           # 20 Right frames
    df.loc[10:14, "dnp09_hz"] = 0.02
    df.loc[60:69, "dnp09_hz"] = 0.02                           # DNp09 above the walk threshold on 15 of them
    df.loc[list(spikes), "gf_spike"] = 1
    return df


def test_rising_edges_and_nearest_offsets():
    assert list(SA.rising_edges([0, 1, 1, 0, 1, 0, 0, 1])) == [1, 4, 7] and list(SA.rising_edges([1, 1, 0])) == [0]
    off = SA.nearest_offsets(np.array([50, 120, 180]), np.array([48, 100, 125]), 30)
    assert off[0] == -2 and off[1] == 5 and np.isnan(off[2])
    assert SA.nearest_offsets(np.array([10]), np.array([7, 13]), 30)[0] == -3          # a tie goes to the earlier spike
    assert np.isnan(SA.nearest_offsets(np.array([10]), np.array([]), 30)[0])


def test_q1_to_q4_known_answers_and_a_not_present_decision():
    df = _synthetic([48, 100, 125])
    res = SA.analyse(df, A_THR, WALK_THR)
    q1, q2, q3, q4 = res["q1"], res["q2"], res["q3"], res["q4"]
    assert q1["a_frames"] == 9 and q1["muscle_over"] == 5 and q1["ttmn_above_rest"] == 7
    assert q2["gf_spike_frames"] == 3 and q2["with_press"] == 2
    assert q2["with_a_held"] == 2
    assert q3["right_frames"] == 20 and q3["dnp09_over"] == 15 and q3["dnp09_over_fraction"] == 0.75
    pp = q4["per_press"]
    assert pp["n"] == 3 and pp["absent"] == 1 and pp["early"] == 1 and pp["late"] == 1 and pp["coincident"] == 0
    assert pp["median_offset_present"] == 1.5 and pp["median_abs_offset"] == 5.0           # [2, 5, inf]
    assert q4["per_frame"]["n"] == 9 and sum(n for _, n in pp["histogram"]) == 2
    dec = res["decision"]
    assert dec["q1_ok"] and dec["q2_ok"] and not dec["q4_ok"] and not dec["present"] and "brain" in dec["gap_in"]


def test_decision_present_when_all_three_hold_and_undefined_is_not_present():
    res = SA.analyse(_synthetic([49, 119, 181]), A_THR, WALK_THR)
    assert res["q2"]["with_press_fraction"] == 1.0 and res["q4"]["per_press"]["median_abs_offset"] == 1.0
    assert res["decision"]["present"] and "motor rule" in res["decision"]["gap_in"]
    none = SA.analyse(_synthetic([]), A_THR, WALK_THR)                                    # no spikes at all: absent
    assert none["q2"]["with_press_fraction"] != none["q2"]["with_press_fraction"] and not none["decision"]["present"]
    assert none["q4"]["per_press"]["absent_fraction"] == 1.0


def test_segments_and_markdown_writer(tmp_path):
    csv = tmp_path / "s.csv"
    df = _synthetic([48, 100, 125]).drop(columns="run")
    df.to_csv(csv, index=False)
    res = SA.write_results([csv], tmp_path / "out.md", A_THR, WALK_THR)
    segs = {s["segment"]: s for s in res["segments"]}
    assert segs["pipe 1"]["reached"] and segs["pipe 1"]["cross_frame"] == 113          # mario_x = 4 * index reaches 448 at index 112
    assert segs["pipe 3"]["reached"] and not segs["gap 1 (pit, 32 px)"]["reached"]     # x only reaches 796
    md = (tmp_path / "out.md").read_text(encoding="utf-8")
    for needle in ("## Q1", "## Q2", "## Q3", "## Q4", "Signals present: NO", "### pipe 1", "gap 1 (pit, 32 px)", "not reached"):
        assert needle in md
