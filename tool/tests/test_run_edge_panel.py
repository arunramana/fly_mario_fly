"""Player edge panels (Brain map / Data / Config): collapse to a tab,
remembered, and -- the point -- never change the video canvas."""
from __future__ import annotations

from PySide6.QtCore import QSettings, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from tool.ui.widgets.run_edge_panel import EdgePanel


def _settings(tmp_path):
    return QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)


def test_open_by_default_and_remembered(qapp, tmp_path):
    s = _settings(tmp_path)
    panel = EdgePanel("data", "Data ▶", QLabel("x"), QSize(100, 50), settings=s)
    assert panel.is_open()
    panel.toggle()
    assert not panel.is_open() and panel.content.isHidden()
    again = EdgePanel("data", "Data ▶", QLabel("x"), QSize(100, 50), settings=s)
    assert not again.is_open()


def test_collapsed_panel_is_just_the_tab(qapp, tmp_path):
    panel = EdgePanel("c", "Config ▶", QLabel("x"), QSize(260, 220), settings=_settings(tmp_path))
    open_h = panel.height()
    panel.set_open(False)
    assert panel.height() < open_h and panel.width() < 260


def test_toggling_panels_never_changes_the_video_canvas(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings as QS
    import tool.ui.widgets.run_edge_panel as mod
    monkeypatch.setattr(mod, "_SETTINGS", _settings(tmp_path))
    from tool.ui.tabs.run import RunTab

    class Win:
        def cancel(self): pass
        def run_batch(self): pass
    tab = RunTab(Win())
    tab.resize(1400, 800)
    tab.show()
    qapp.processEvents()
    pix = QPixmap(256, 240)
    pix.fill()
    tab.player.canvas.set_pixmap(pix)
    qapp.processEvents()
    before = (tab.player.canvas.geometry(), tab.player.canvas.target_rect())
    for panel in (tab.brain_overlay, tab.data_overlay, tab.config_overlay):
        for _ in range(2):
            panel.toggle()
            qapp.processEvents()
            assert (tab.player.canvas.geometry(), tab.player.canvas.target_rect()) == before
    tab.resize(500, 800)  # too narrow for the margins: still overlaps, video rect logic unchanged
    qapp.processEvents()
    assert tab.player.canvas.target_rect().width() % 256 == 0
    tab.close()


def test_panels_fill_the_margin_full_height(qapp, tmp_path, monkeypatch):
    import tool.ui.widgets.run_edge_panel as mod
    monkeypatch.setattr(mod, "_SETTINGS", _settings(tmp_path))
    from tool.ui.tabs.run import RunTab

    class Win:
        def cancel(self): pass
        def run_batch(self): pass
    tab = RunTab(Win())
    tab.resize(1800, 900)
    tab.show()
    pix = QPixmap(256, 240)
    pix.fill()
    tab.player.canvas.set_pixmap(pix)
    qapp.processEvents()
    tab._place_panels()
    canvas = tab.player.canvas
    margin = (canvas.width() - canvas.target_rect().width()) // 2
    assert tab.brain_overlay.width() == margin
    assert tab.brain_overlay.height() >= canvas.height() - 80
    assert tab.data_overlay.width() == margin == tab.config_overlay.width()
    tab.close()
