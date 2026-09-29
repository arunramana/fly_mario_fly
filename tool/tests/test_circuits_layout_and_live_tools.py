"""Tool-only sprint: Circuits tab page scroll/inspector, batch summary table, fps meter,
latest-frame-only live rendering, controller pad from the action index, duplicate copying
save states."""
from __future__ import annotations

import queue
import shutil

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea

from config.output_routing import PROJECTS_ROOT
from config.params import CONTROL_RULE_LABELS
from tool.core.circuit_manifest import CIRCUIT_REGISTRY, OTHER_ENTRY

NAME = "_layout_live_tools_test"


@pytest.fixture
def window(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    w = MainWindow(ToolProject.create(NAME))
    qtbot.addWidget(w)
    w._closing_confirmed = True       # a dirty window would open a save/discard dialog on close
    yield w
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def _wheel(widget):
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    widget.wheelEvent(ev)
    return ev


# ---- Circuits tab: one page scroll, wheel never edits a field -------------------------------

def test_circuits_tab_is_one_page_scroll_with_no_nested_scroll_areas(window):
    circuits = window.tabs.widget(3)
    assert circuits.findChildren(QScrollArea) == [circuits.page_scroll]
    assert circuits.page_scroll.widgetResizable()


def test_wheel_over_an_unfocused_field_scrolls_the_page_not_the_value(window):
    circuits = window.tabs.widget(3)
    for spin in (circuits.shuffle_seed_spin, circuits.module_editors[("wall_ahead", "looming_gain")],
                 circuits.param_form._widget_by_path["jump.g"]):
        before = spin.value()
        ev = _wheel(spin)
        assert not ev.isAccepted(), "an ignored wheel bubbles up to the page scroll area"
        assert spin.value() == before


def test_every_module_and_rule_has_exactly_one_home_card():
    from tool.ui.tabs.circuits import MODULE_TOGGLES
    entries = [*CIRCUIT_REGISTRY, OTHER_ENTRY]
    for field in [m[0] for m in MODULE_TOGGLES]:
        assert sum(field in e.modules for e in entries) == 1, field
    for rule in [*CONTROL_RULE_LABELS, "graded_pit_response"]:
        assert sum(rule in e.rules for e in entries) == 1, rule


def test_inspector_shows_the_selected_circuits_modules_rules_and_badges(window):
    circuits = window.tabs.widget(3)
    circuits._select_circuit("jump")
    assert "Control rules (3/3 on)" in circuits.rules_section.toggle.text()
    assert "Controller modules (0/5 on)" in circuits.modules_section.toggle.text()
    assert not circuits._module_rows["wall_ahead"].isHidden() and circuits._module_rows["gap_ahead"].isHidden()
    circuits.rule_checkboxes["jump_hold"].setChecked(False)
    assert "Control rules (2/3 on)" in circuits.rules_section.toggle.text()
    circuits.module_checkboxes["wall_ahead"].setChecked(True)
    assert "Controller modules (1/5 on)" in circuits.modules_section.toggle.text()
    circuits._select_circuit("mdn")
    assert circuits.modules_section.isHidden() and not circuits.rules_section.isHidden()


def test_module_slider_and_spin_stay_in_sync(window):
    circuits = window.tabs.widget(3)
    circuits.module_checkboxes["wall_ahead"].setChecked(True)
    spin = circuits.module_editors[("wall_ahead", "looming_gain")]
    slider = circuits._module_sliders[("wall_ahead", "looming_gain")]
    slider.setValue(500)                                        # half of 0..10
    assert spin.value() == pytest.approx(5.0)
    assert window.get_config().modules.wall_ahead.looming_gain == pytest.approx(5.0)
    spin.setValue(10.0)
    assert slider.value() == slider.maximum()


def test_shuffle_is_a_small_switch(window):
    assert window.tabs.widget(3).shuffle_checkbox.objectName() == "switch"


# ---- batch summary --------------------------------------------------------------------------

def _entry(number, seed, max_x, flag, batch="b1"):
    return {"number": number, "seed": seed, "batch_id": batch,
            "summary": {"max_x_abs": max_x, "flag_get": flag, "n_frames": 500 + seed, "n_stomps": seed,
                        "n_escape_jumps": 2 * seed}}


def test_batch_rows_and_stats_group_by_batch_id():
    from tool.core.batch_summary import batch_rows, batch_stats, entries_in_batch
    entries = [_entry(3, 2, 900, False), _entry(1, 0, 3000, True), _entry(2, 1, 1500, True),
               _entry(4, 0, 100, False, batch="other"), {"number": 5, "seed": 0, "summary": {}}]
    rows = batch_rows(entries_in_batch(entries, "b1"))
    assert [r[0] for r in rows] == [0, 1, 2] and rows[0] == (0, 3000, True, 500, 0, 0)
    assert batch_stats(rows) == (2, 3, pytest.approx(1800.0))
    assert entries_in_batch(entries, None) == []


def test_batch_table_shows_for_a_batch_run_and_hides_for_a_plain_one(window):
    run_tab = window.run_tab
    entries = [_entry(1, 0, 3000, True), _entry(2, 1, 1000, False),
               {"number": 3, "seed": 0, "batch_id": None, "summary": {"max_x_abs": 50}}]
    run_tab._entries = entries
    run_tab.show_batch_for(2)
    table = run_tab.batch_table
    assert not table.isHidden() and table.table.rowCount() == 2
    assert [table.table.horizontalHeaderItem(c).text() for c in range(6)] == [
        "seed", "max_x", "flag", "frames", "stomps", "escape jumps"]
    assert "wins: 1 / 2" in table.totals_label.text() and "mean max_x: 2000" in table.totals_label.text()
    run_tab.show_batch_for(3)
    assert table.isHidden()


# ---- fps meter and latest-frame-only rendering ----------------------------------------------

def test_fps_meter_separates_sim_rate_from_displayed_rate():
    from tool.core.fps_meter import FpsMeter
    t = [0.0]
    m = FpsMeter(window_s=1.0, clock=lambda: t[0])
    for i in range(11):                 # 100 sim frames over 0.5 s = 200 fps; 5 draws
        t[0] = i * 0.05
        m.sim_frame(i * 10)
        if i % 2 == 0 and i:
            m.shown_frame()
    sim, shown = m.rates()
    assert sim == pytest.approx(200.0) and shown == pytest.approx(5.0)
    t[0] = 10.0
    assert m.rates() == (0.0, 0.0)


def test_poll_queue_draws_only_the_latest_frame_but_tracks_it(window, monkeypatch):
    shown = []
    monkeypatch.setattr(window.run_tab.preview, "show_frame", lambda obs, row: shown.append(row["frame"]))
    window._queue = queue.Queue()
    for f in range(5):
        window._queue.put(("frame", np.zeros((4, 4, 3), dtype=np.uint8), {"frame": f}))
    window._poll_queue()
    assert shown == [4]
    assert window.run_tab.progress.value() == int(100 * 4 / window.project.config.scenario.max_frames)
    assert "displayed" in window.run_tab.fps_label.text()


# ---- controller pad from the action index ---------------------------------------------------

@pytest.mark.parametrize("action,expected", [(0, (False, True, False, False)), (3, (False, True, True, True)),
                                             (4, (True, False, False, False)), (6, (True, False, False, True)),
                                             (None, (False, False, False, False))])
def test_pad_lights_from_the_action_index(qtbot, action, expected):
    from tool.ui.widgets.controller_pad import ControllerPad
    from mario.actions.actions import MOVES
    pad = ControllerPad()
    qtbot.addWidget(pad)
    pad.set_from_action(action)
    assert pad.state() == expected
    if action is not None:               # agrees with the emulator's own action table
        buttons = MOVES[action]
        assert pad.state() == ("left" in buttons, "right" in buttons, "B" in buttons, "A" in buttons)


# ---- duplicate copies save states -----------------------------------------------------------

def test_duplicate_copies_savestates_and_entity_profiles():
    from tool.core.project import ToolProject
    from tool.core.savestates import list_states, save_state
    src_name, dup_name = "_dup_src_test", "_dup_dst_test"
    for n in (src_name, dup_name):
        shutil.rmtree(PROJECTS_ROOT / n, ignore_errors=True)
    try:
        src = ToolProject.create(src_name)
        save_state(src_name, "s1", [0, 1, 2], "1-1", 3)
        (PROJECTS_ROOT / src_name / "entity_profiles.json").write_text("{}", encoding="utf-8")
        src.duplicate(dup_name)
        assert list_states(dup_name) == ["s1"]
        assert (PROJECTS_ROOT / dup_name / "entity_profiles.json").exists()
    finally:
        for n in (src_name, dup_name):
            shutil.rmtree(PROJECTS_ROOT / n, ignore_errors=True)
