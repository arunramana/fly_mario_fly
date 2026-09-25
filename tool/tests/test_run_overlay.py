"""tool/ui/widgets/run_overlay.py -- movable/resizable/dockable overlay
panel (Brain map/Data/Config). Uses an isolated, tmp_path-backed QSettings
per test -- the real one persists to this machine's own per-user config
store and must never be touched or depended on by a test.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel

from tool.ui.widgets.run_overlay import OverlayPanel


def _isolated_settings(tmp_path):
    return QSettings(str(tmp_path / "overlay_test.ini"), QSettings.Format.IniFormat)


def test_starts_docked_and_hidden(qapp, tmp_path):
    panel = OverlayPanel("brain_map", "Brain map", QLabel("content"), settings=_isolated_settings(tmp_path))
    assert panel.is_docked()
    assert not panel.isVisible()


def test_show_panel_makes_it_visible(qapp, tmp_path):
    panel = OverlayPanel("data", "Data", QLabel("content"), settings=_isolated_settings(tmp_path))
    panel.show_panel()
    assert panel.isVisible()
    panel.hide_panel()
    assert not panel.isVisible()


def test_toggle_visible_flips_state(qapp, tmp_path):
    panel = OverlayPanel("config", "Config", QLabel("content"), settings=_isolated_settings(tmp_path))
    panel.toggle_visible()
    assert panel.isVisible()
    panel.toggle_visible()
    assert not panel.isVisible()


def test_toggle_docked_flips_state_and_emits(qapp, tmp_path):
    panel = OverlayPanel("brain_map", "Brain map", QLabel("content"), settings=_isolated_settings(tmp_path))
    seen = []
    panel.docked_changed.connect(seen.append)
    assert panel.is_docked()
    panel.toggle_docked()
    assert not panel.is_docked()
    assert seen == [False]
    panel.toggle_docked()
    assert panel.is_docked()
    assert seen == [False, True]


def test_docked_state_persists_across_instances(qapp, tmp_path):
    settings = _isolated_settings(tmp_path)
    panel = OverlayPanel("data", "Data", QLabel("content"), settings=settings)
    panel.set_docked(False)

    panel2 = OverlayPanel("data", "Data", QLabel("content 2"), settings=settings)
    assert not panel2.is_docked(), "a new instance should pick up the remembered dock state"


def test_close_button_hides_and_emits_closed(qapp, tmp_path):
    panel = OverlayPanel("config", "Config", QLabel("content"), settings=_isolated_settings(tmp_path))
    panel.show_panel()
    seen = []
    panel.closed.connect(lambda: seen.append(True))
    panel.close_button.click()
    assert not panel.isVisible()
    assert seen == [True]
