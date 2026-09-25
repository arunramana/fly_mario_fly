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
