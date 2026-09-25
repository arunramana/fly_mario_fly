"""Ease-of-use redesign, smaller Run tab pieces: the scrub timeline
(clicking seeks, markers draw), the collapsible drawer (open/close,
remembered width), the Data/Config text panels, and RunTable's prev/next
+ batch-grouping additions.
"""
from __future__ import annotations

import dataclasses

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel

from config.project_config import ProjectConfig
from tool.ui.widgets.collapsible_drawer import CollapsibleDrawer
from tool.ui.widgets.run_detail_panels import ConfigDiffPanel, DataPanel
from tool.ui.widgets.run_table import RunTable
from tool.ui.widgets.video_timeline import VideoTimeline


def _click_event(x: float) -> QMouseEvent:
    return QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(x, 5), QPointF(x, 5),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)


def test_timeline_click_seeks_proportionally(qapp):
    timeline = VideoTimeline()
    timeline.resize(100, 30)
    timeline.set_length(101)  # frame == x, for an easy assertion
    seen = []
    timeline.seek_requested.connect(seen.append)
    timeline.mousePressEvent(_click_event(50))
    assert seen == [50]


def test_timeline_set_position_clamps_to_length(qapp):
    timeline = VideoTimeline()
    timeline.set_length(10)
    timeline.set_position(999)
    assert timeline._position == 9
    timeline.set_position(-5)
    assert timeline._position == 0


def test_timeline_markers_stored_by_type(qapp):
    timeline = VideoTimeline()
    timeline.set_length(100)
    timeline.set_markers({"jump": [1, 2], "climb": [3]})
    assert timeline._markers["jump"] == [1, 2]
    assert timeline._markers.get("stomp") is None


def test_collapsible_drawer_toggle(qapp):
    content = QLabel("content")
    drawer = CollapsibleDrawer("Test", content, open=True, width=300)
    assert drawer.is_open()
    assert not content.isHidden()

    fired = []
    drawer.toggled.connect(fired.append)
    drawer.set_open(False)
    assert not drawer.is_open()
    assert content.isHidden()
    assert fired == [False]


def test_collapsible_drawer_remembers_width(qapp):
    content = QLabel("content")
    drawer = CollapsibleDrawer("Test", content, open=True, width=250)
    assert drawer.width_when_open() == 250
    drawer.set_width_when_open(400)
    assert drawer.width_when_open() == 400


def test_data_panel_shows_row_and_summary(qapp):
    panel = DataPanel()
    panel.set_content({"frame": 5, "mario_x": 100}, {"n_frames": 10, "died_or_flagged": False})
    html = panel.toHtml()
    assert "frame = 5" in html
    assert "n_frames = 10" in html


def test_data_panel_handles_nothing_selected(qapp):
    panel = DataPanel()
    panel.set_content(None, None)
    assert "no run selected" in panel.toPlainText() or "no frame" in panel.toPlainText()


def test_config_diff_panel_shows_only_differing_fields(qapp):
    panel = ConfigDiffPanel()
    config = dataclasses.replace(ProjectConfig(), jump=dataclasses.replace(ProjectConfig().jump, g=2.7))
    panel.set_config(config)
    text = panel.toPlainText()
    assert "jump.g" in text
    assert "2.7" in text
    assert "network.alpha" not in text, "unchanged fields must not clutter the diff"


def test_config_diff_panel_all_defaults_says_so(qapp):
    panel = ConfigDiffPanel()
    panel.set_config(ProjectConfig())
    assert "default" in panel.toPlainText().lower()


def _entry(number, seed=0, batch_id=None, cancelled=False):
    return {
        "number": number, "seed": seed, "batch_id": batch_id, "time": "2026-01-01T00:00:00",
        "summary": {"n_frames": 100, "max_x_abs": 500.0, "died_or_flagged": False, "cancelled": cancelled},
        "run_spec": {"tool_settings": {"fitness": {"points": 0.0, "distance": 1.0, "time": 0.0}}},
    }


def test_run_table_select_number_and_adjacent(qapp):
    table = RunTable()
    table.set_entries([_entry(1), _entry(2), _entry(3)])
    assert table.select_number(2)
    assert table.selected_number() == 2

    table.select_adjacent(1)
    first_neighbor = table.selected_number()
    assert first_neighbor != 2
    assert not table.select_number(999)


def test_run_table_batch_column_shows_batch_id(qapp):
    table = RunTable()
    table.set_entries([_entry(1, batch_id="abc123"), _entry(2, batch_id=None)])
    batch_col = table.COLUMNS.index("batch") if hasattr(table, "COLUMNS") else None
    from tool.ui.widgets.run_table import COLUMNS
    batch_col = COLUMNS.index("batch")
    values = {table.item(row, 0).data(Qt.ItemDataRole.UserRole)["number"]: table.item(row, batch_col).text()
              for row in range(table.rowCount())}
    assert values[1] == "abc123"
    assert values[2] == ""
