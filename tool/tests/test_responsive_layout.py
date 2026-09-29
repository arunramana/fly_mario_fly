"""Responsive layout: the tool must fit a small / high-DPI laptop screen, not just a big monitor."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSettings, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from tool.ui.app import MIN_FONT_SCALE, _scale_points, font_scale_for
from tool.ui.screen_fit import MIN_WINDOW, apply_initial_geometry, centered_fraction, clamp_to
from tool.ui.tabs.circuits import CARD_ICON_MIN_PX, CARD_ICON_PX, card_icon_px
from tool.ui.widgets.reflow_grid import ReflowGrid
from tool.ui.widgets.run_edge_panel import EdgePanel
from tool.ui.widgets.video_canvas import VideoCanvas


def _settings(tmp_path):
    return QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)


def test_opens_at_90_percent_centered():
    avail = QRect(0, 0, 1707, 928)
    r = centered_fraction(avail)
    assert (r.width(), r.height()) == (1536, 835)
    assert r.center().x() - avail.center().x() in (-1, 0, 1)
    assert avail.contains(r)


def test_saved_geometry_is_clamped_to_the_current_screen():
    small = QRect(0, 0, 1280, 700)
    r = clamp_to(small, QRect(1500, 900, 1920, 1080))   # saved on a bigger, second monitor
    assert small.contains(r) and r.width() == 1280 and r.height() == 700


def test_minimum_size_never_exceeds_the_documented_cap(qapp, tmp_path):
    w = QWidget()
    apply_initial_geometry(w, _settings(tmp_path))
    assert w.minimumWidth() <= MIN_WINDOW[0] and w.minimumHeight() <= MIN_WINDOW[1]
    avail = w.screen().availableGeometry()
    assert avail.contains(w.geometry())


def test_reflow_grid_column_count_follows_width(qapp):
    grid = ReflowGrid(cell_width=100, spacing=10)
    for i in range(7):
        grid.add(QPushButton(str(i)))
    assert grid.columns_for(100) == 1 and grid.columns_for(330) == 3 and grid.columns_for(50) == 1
    grid.resize(330, 400)
    grid.show()
    qapp.processEvents()
    assert grid.columns == 3
    grid.resize(120, 400)
    qapp.processEvents()
    assert grid.columns == 1
    assert grid.minimumSizeHint().width() == 100   # one card, so it can shrink to a single column
    grid.close()


def test_card_icon_scales_with_screen():
    assert card_icon_px(2560) == CARD_ICON_PX
    assert card_icon_px(1280) < CARD_ICON_PX
    assert card_icon_px(400) == CARD_ICON_MIN_PX


def test_font_scale_only_shrinks_and_is_floored():
    assert font_scale_for(2560) == 1.0 and font_scale_for(300) == MIN_FONT_SCALE
    assert "8.0pt" in _scale_points("font-size: 10pt;", 0.8)


def test_video_canvas_scales_below_1x_keeping_aspect(qapp):
    canvas = VideoCanvas()
    pix = QPixmap(256, 240)
    pix.fill()
    canvas.set_pixmap(pix)
    canvas.resize(128, 120)
    r = canvas.target_rect()
    assert canvas.rect().contains(r) and r.width() == 128 and r.height() == 120
    canvas.resize(200, 100)   # short and wide: height limits, aspect kept
    r = canvas.target_rect()
    assert canvas.rect().contains(r) and abs(r.width() / r.height() - 256 / 240) < 0.05
    canvas.resize(800, 500)   # big: whole-number scale-up unchanged
    assert canvas.target_rect().width() % 256 == 0


def test_drawer_width_is_remembered_as_a_fraction(qapp, tmp_path):
    s = _settings(tmp_path)
    panel = EdgePanel("d", "D", QLabel("x"), QSize(100, 50), settings=s)
    panel.set_width_fraction(0.3)
    again = EdgePanel("d", "D", QLabel("x"), QSize(100, 50), settings=s)
    assert again.width_fraction() == 0.3
    assert again.min_width_for(2000) >= 600 and again.min_width_for(1000) >= 300   # scales with the canvas
    again.set_width_fraction(9)
    assert again.width_fraction() == 0.45   # clamped
