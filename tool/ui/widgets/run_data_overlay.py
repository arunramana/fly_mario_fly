"""tool/ui/widgets/run_data_overlay.py -- Run tab / player redesign: the
Data overlay's content -- a compact, see-through readout of the current
frame's x, speed, buttons pressed, and top active neurons. Replaces the
old neuron activity strip as a persistent fixture; reuses its own
calibrated per-population max values (tool/ui/widgets/
neuron_activity_strip.py's BARS) for the "top active" ranking instead of
re-deriving a second set of ceilings.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from tool.ui.widgets.neuron_activity_strip import BARS

TOP_N = 4


class DataOverlayContent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dataOverlayContent")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        self._lines = QLabel("(no frame)")
        self._lines.setWordWrap(True)
        layout.addWidget(self._lines)

    def update_from_row(self, row: dict | None) -> None:
        if not row:
            self._lines.setText("(no frame)")
            return
        x = row.get("mario_x")
        direction = row.get("direction", "?")
        press_a = "A" if row.get("press_a") or row.get("long_jump") else "-"
        press_b = "B" if row.get("press_b") else "-"
        speed = row.get("dnp09")
        ranked = []
        for key, label, max_value in BARS:
            value = row.get(key)
            if value is None or max_value <= 0:
                continue
            ranked.append((abs(float(value)) / max_value, label, value))
        ranked.sort(reverse=True)

        lines = [
            f"x = {x}   dir = {direction}",
            f"buttons = {direction}{press_a}{press_b}   speed(DNp09) = {_fmt(speed)}",
            "top active:",
        ]
        for _pct, label, value in ranked[:TOP_N]:
            lines.append(f"  {label} = {_fmt(value)}")
        self._lines.setText("\n".join(lines))


def _fmt(value) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
