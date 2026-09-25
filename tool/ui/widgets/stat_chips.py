"""tool/ui/widgets/stat_chips.py -- ease-of-use redesign: compact result
chips above the Run tab's player (distance, fitness, frames, died/
flagged) -- replaces the old free-text result line as the AT-A-GLANCE
summary; show_result()'s own text (main_window.py) still exists for the
fuller sentence, kept as a secondary line below the chips.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StatChips(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._labels: dict[str, QLabel] = {}
        for key in ("distance", "fitness", "frames", "outcome"):
            label = QLabel("--")
            label.setObjectName("statChip")
            layout.addWidget(label)
            self._labels[key] = label
        layout.addStretch(1)

    def set_summary(self, summary: dict | None, fitness: float | None = None) -> None:
        if not summary:
            for label in self._labels.values():
                label.setText("--")
            return
        self._labels["distance"].setText(f"distance {summary.get('max_x_abs', 0):.0f}px")
        self._labels["fitness"].setText(f"fitness {fitness:.1f}" if fitness is not None else "fitness --")
        self._labels["frames"].setText(f"frames {summary.get('n_frames', '-')}")
        if summary.get("cancelled"):
            outcome = "CANCELLED"
        elif summary.get("died_or_flagged"):
            outcome = "died/flagged"
        else:
            outcome = "survived"
        self._labels["outcome"].setText(outcome)
