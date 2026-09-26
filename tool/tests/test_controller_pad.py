"""The controller overlay: ◀ ▶ B A lit from telemetry, toggled with I, never resizing the video."""
from __future__ import annotations

import shutil

import pandas as pd
from PySide6.QtGui import QKeySequence, QShortcut

from config.output_routing import PROJECTS_ROOT
from tool.ui.widgets.controller_pad import ControllerPad

NAME = "_controller_pad_test"


def test_pad_lights_buttons_from_a_row(qapp):
    pad = ControllerPad()
    pad.set_from_row({"direction": "R", "press_b": True, "press_a": False})
    assert pad.state() == (False, True, True, False)                 # ▶ and B
    pad.set_from_row(pd.Series({"direction": "L", "press_b": False, "press_a": True}))
    assert pad.state() == (True, False, False, True)                 # ◀ and A (a telemetry Series works too)
    pad.set_from_row(None)
    assert pad.state() == (False, False, False, False)


def _window(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    window = MainWindow(ToolProject.create(NAME))
    qtbot.addWidget(window)
    window._closing_confirmed = True
    return window


def test_on_by_default_toggle_and_video_never_resizes(qtbot):
    window = _window(qtbot)
    try:
        tab = window.run_tab
        window.show()
        qtbot.waitExposed(window)
        canvas = tab.player.canvas
        assert not tab.controller_pad.isHidden()                       # on by default
        rect = canvas.target_rect()
        assert rect.contains(tab.controller_pad.geometry())            # sits inside the video's bottom strip
        assert tab.controller_pad.geometry().center().y() > rect.center().y()
        tab.toggle_controller_overlay()
        assert tab.controller_pad.isHidden() and canvas.target_rect() == rect
        tab.toggle_controller_overlay()
        assert not tab.controller_pad.isHidden() and canvas.target_rect() == rect
        # exactly one shortcut for I, and it toggles
        shortcuts = [s for s in window.findChildren(QShortcut) if s.key() == QKeySequence("I")]
        assert len(shortcuts) == 1
        shortcuts[0].activated.emit()
        assert tab.controller_pad.isHidden()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_pad_follows_live_rows_and_seeked_frames(qtbot, tmp_path):
    import numpy as np
    window = _window(qtbot)
    try:
        tab = window.run_tab
        tab._on_live_row({"direction": "L", "press_b": True, "press_a": True})      # a live run
        assert tab.controller_pad.state() == (True, False, True, True)
        tel = pd.read_csv(PROJECTS_ROOT / "win_attempt" / "telemetry" / "033_first_win_telemetry.csv").head(60)
        raw = tmp_path / "frames.npz"                                   # a tiny recording so the player is seekable
        np.savez(raw, frames=np.zeros((60, 240, 256), dtype=np.uint8), palette=np.zeros((1, 3), dtype=np.uint8))
        tab.load_run_data(str(raw), tel, {"n_frames": 60}, None)
        for frame in (10, 40):
            tab.player._refresh_frame_display(frame)
            row = tel.iloc[frame]
            assert tab.controller_pad.state() == (row.direction == "L", row.direction == "R",
                                                  bool(row.press_b), bool(row.press_a))
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
