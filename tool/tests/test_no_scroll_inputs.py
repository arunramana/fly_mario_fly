"""Found live in projects/legacy/config.json: scrolling PAST a field (no
click, no focus) silently changed its value. NoScroll* widgets ignore an
unfocused wheel event (letting it bubble to a parent QScrollArea instead
of being consumed); ScientificDoubleSpinBox displays a very small value
in scientific notation rather than rounding it to a lying "0.00".
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from tool.ui.widgets.no_scroll_inputs import (
    NoScrollDoubleSpinBox, NoScrollSlider, NoScrollSpinBox, ScientificDoubleSpinBox,
)


def _wheel_event(delta: int = 120) -> QWheelEvent:
    return QWheelEvent(QPointF(0, 0), QPointF(0, 0), QPoint(0, 0), QPoint(0, delta),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)


@pytest.mark.parametrize("cls,setup", [
    (NoScrollSpinBox, lambda w: (w.setRange(0, 100), w.setValue(5))),
    (NoScrollDoubleSpinBox, lambda w: (w.setRange(0.0, 100.0), w.setValue(5.0))),
])
def test_unfocused_spin_box_ignores_wheel(qapp, cls, setup):
    widget = cls()
    setup(widget)
    original = widget.value()
    assert not widget.hasFocus()

    event = _wheel_event()
    widget.wheelEvent(event)

    assert widget.value() == original, "an unfocused spin box must not change value on scroll"
    assert not event.isAccepted(), "the ignored event must bubble to a parent (e.g. a QScrollArea)"


def test_focused_spin_box_still_responds_to_wheel(qapp, qtbot):
    widget = NoScrollDoubleSpinBox()
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    qtbot.addWidget(widget)
    widget.show()
    widget.setFocus()
    qtbot.waitUntil(widget.hasFocus, timeout=1000)

    widget.wheelEvent(_wheel_event())
    assert widget.value() != 5.0, "a deliberately focused spin box should still scroll"


def test_unfocused_slider_ignores_wheel(qapp):
    slider = NoScrollSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(50)
    assert not slider.hasFocus()

    event = _wheel_event()
    slider.wheelEvent(event)

    assert slider.value() == 50
    assert not event.isAccepted()


def test_no_scroll_widgets_have_strong_focus_policy(qapp):
    assert NoScrollSpinBox().focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert NoScrollDoubleSpinBox().focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert NoScrollSlider(Qt.Orientation.Horizontal).focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_scientific_spin_box_displays_tiny_values_without_rounding_to_zero(qapp):
    spin = ScientificDoubleSpinBox()
    spin.setRange(-1e9, 1e9)
    spin.setValue(1e-30)
    assert spin.value() == pytest.approx(1e-30)
    assert spin.text() == "1.00e-30"
    assert "0.00" not in spin.text()


def test_scientific_spin_box_round_trips_typed_text(qapp):
    spin = ScientificDoubleSpinBox()
    spin.setRange(-1e9, 1e9)
    assert spin.valueFromText("1.5e-6") == pytest.approx(1.5e-6)
