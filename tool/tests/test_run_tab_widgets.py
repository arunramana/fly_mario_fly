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


# ---- modules on/off in the Config diff, and load_run_data ordering ----------

def _with_modules(**mods):
    from config.params import ModulesConfig
    return dataclasses.replace(ProjectConfig(), modules=ModulesConfig(**mods))


def test_diff_reports_a_whole_module_as_off_to_set_and_back():
    from config.params import GapAheadParams
    from tool.ui.widgets.run_detail_panels import _diff_dataclass
    on, off = _with_modules(gap_ahead=GapAheadParams()), ProjectConfig()
    diffs = {p: (v, d) for p, v, d in _diff_dataclass(on, off)}
    assert list(diffs) == ["modules.gap_ahead"]                      # not modules.gap_ahead.perceive_tiles
    assert diffs["modules.gap_ahead"] == (GapAheadParams(), None)
    back = {p: (v, d) for p, v, d in _diff_dataclass(off, on)}
    assert back["modules.gap_ahead"] == (None, GapAheadParams())


def test_config_panel_renders_off_arrow_and_arrow_off(qapp):
    from config.params import GapAheadParams
    panel = ConfigDiffPanel()
    panel.set_config(_with_modules(gap_ahead=GapAheadParams(perceive_tiles=4)))
    panel.set_changed_only(True)
    assert "gap_ahead: off → {'perceive_tiles': 4}" in panel.toPlainText()
    # a config whose module is off, compared with defaults that have it on
    # (default() is the shipped one, so emulate with the reverse helper)
    from tool.ui.widgets.run_detail_panels import _row
    import html
    assert "{'perceive_tiles': 4} → off" in html.unescape(
        _row("gap_ahead", None, GapAheadParams(perceive_tiles=4), True))


def test_load_run_data_with_perception_modules_on_updates_every_panel(qtbot):
    import pandas as pd
    from config.params import GapAheadParams, PagePerceptionParams
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    from config.output_routing import PROJECTS_ROOT
    import shutil
    name = "_load_run_modules_test"
    shutil.rmtree(PROJECTS_ROOT / name, ignore_errors=True)
    try:
        window = MainWindow(ToolProject.create(name))
        qtbot.addWidget(window)
        window._closing_confirmed = True
        tab = window.run_tab
        tel = pd.read_csv(PROJECTS_ROOT / "win_attempt" / "telemetry" / "033_first_win_telemetry.csv").head(40)
        cfg = _with_modules(gap_ahead=GapAheadParams(), page_perception=PagePerceptionParams())
        info = {"n_frames": 40, "max_x_abs": 123, "died_or_flagged": True}
        tab.load_run_data(None, tel, info, cfg)
        text = tab.config_content.panel.toPlainText()
        assert "gap_ahead" in text and "page_perception" in text and "→" in text
        assert tab.data_content._summary == info                      # summary updated by load_run_data itself
        assert tab.brain_map_content._panel_ctx is not None            # later panels still refreshed
        # a config that cannot be rendered must not leave the rest stale
        tab.load_run_data(None, tel, {"n_frames": 40, "max_x_abs": 7}, object())
        assert "config could not be shown" in tab.config_content.panel.toPlainText()
        assert tab.data_content._summary["max_x_abs"] == 7
        assert tab.brain_map_content._panel_ctx is not None
    finally:
        shutil.rmtree(PROJECTS_ROOT / name, ignore_errors=True)
