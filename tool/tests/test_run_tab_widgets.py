"""Run tab / player redesign, smaller pieces still used directly: the
scrub timeline (clicking seeks, markers draw) and the Config overlay's
diff panel. CollapsibleDrawer/DataPanel/RunTable (the old drawer-based
design) are gone -- see tool/ui/widgets/run_edge_panel.py, run_data_
overlay.py, and run_playlist.py for their replacements' own tests.
"""
from __future__ import annotations

import dataclasses

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from config.project_config import ProjectConfig
from tool.ui.widgets.run_detail_panels import ConfigDiffPanel
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


def _cfg(**jump):
    return dataclasses.replace(ProjectConfig(), jump=dataclasses.replace(ProjectConfig().jump, **jump))


def test_config_changed_only_shows_only_differing_fields(qapp):
    panel = ConfigDiffPanel()
    panel.set_config(_cfg(g=2.7))
    panel.set_changed_only(True)
    text = panel.toPlainText()
    assert "[jump]" in text and "g = 2.7" in text
    assert "[network]" not in text, "unchanged sections must not clutter the diff"


def test_config_full_view_lists_everything_and_highlights_changes(qapp):
    panel = ConfigDiffPanel()
    panel.set_config(_cfg(g=2.7))
    text = panel.toPlainText()
    assert "[network]" in text and "[scenario]" in text and "alpha" in text
    assert "background-color:#c8a000" in panel.toHtml().replace(" ", "") or "c8a000" in panel.toHtml()


def test_config_changed_only_all_defaults_says_so(qapp):
    panel = ConfigDiffPanel()
    panel.set_config(ProjectConfig())
    panel.set_changed_only(True)
    assert "default" in panel.toPlainText().lower()


def test_config_shows_the_runs_own_level_not_the_projects(qapp):
    cfg = dataclasses.replace(ProjectConfig(), scenario=dataclasses.replace(ProjectConfig().scenario, level="1-3"))
    panel = ConfigDiffPanel()
    panel.set_config(cfg)
    assert "level = 1-3" in panel.toPlainText()
