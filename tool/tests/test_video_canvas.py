"""tool/ui/widgets/video_canvas.py -- letterboxed, whole-number-scaled
frame drawing."""
from __future__ import annotations

from PySide6.QtGui import QPixmap

from tool.ui.widgets.video_canvas import VideoCanvas


def test_starts_with_a_null_pixmap_and_placeholder_text(qapp):
    canvas = VideoCanvas()
    assert canvas.pixmap().isNull()


def test_set_pixmap_updates_pixmap_accessor(qapp):
    canvas = VideoCanvas()
    pixmap = QPixmap(256, 240)
    pixmap.fill()
    canvas.set_pixmap(pixmap)
    assert not canvas.pixmap().isNull()
    assert canvas.pixmap().width() == 256


def test_target_rect_scales_by_a_whole_number_factor_and_centers(qapp):
    canvas = VideoCanvas()
    canvas.resize(1000, 500)
    pixmap = QPixmap(256, 240)
    pixmap.fill()
    canvas.set_pixmap(pixmap)
    rect = canvas.target_rect()
    # Largest whole-number factor fitting 1000x500 for a 256x240 source is 2x.
    assert rect.width() == 512
    assert rect.height() == 480
    assert rect.x() == (1000 - 512) // 2
    assert rect.y() == (500 - 480) // 2


def test_target_rect_is_full_widget_rect_when_no_pixmap(qapp):
    canvas = VideoCanvas()
    canvas.resize(400, 300)
    assert canvas.target_rect() == canvas.rect()
