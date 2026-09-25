"""tool/ui/widgets/run_picker.py -- the Player's top-bar run switcher: a
dropdown ("#N · seed · max_x · fitness · outcome", newest first, batch runs
grouped under a header row) with previous/next buttons. Replaces the
sliding thumbnail playlist.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget


def label_for(entry: dict) -> str:
    summary = entry.get("summary", {})
    if summary.get("cancelled"):
        outcome = "cancelled"
    elif summary.get("died_or_flagged") and summary.get("flag_get"):
        outcome = "flag"
    elif summary.get("died_or_flagged"):
        outcome = "died"
    else:
        outcome = "survived"
    fitness = entry.get("fitness")
    fit = f"{fitness:.0f}" if isinstance(fitness, (int, float)) else "--"
    max_x = summary.get("max_x_abs")
    max_x = f"{max_x:.0f}" if isinstance(max_x, (int, float)) else "?"
    return f"#{entry['number']} · seed {entry.get('seed', '?')} · x {max_x} · fit {fit} · {outcome}"


class RunPicker(QWidget):
    run_selected = Signal(int)  # run number

    def __init__(self, parent=None):
        super().__init__(parent)
        self._numbers: list[int] = []  # ascending
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        self.prev_button = QPushButton("◀")
        self.prev_button.setToolTip("Previous run")
        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(420)
        self.combo.activated.connect(self._on_activated)
        self.next_button = QPushButton("▶")
        self.next_button.setToolTip("Next run")
        self.next_button.clicked.connect(lambda: self._step(1))
        row.addWidget(self.prev_button)
        row.addWidget(self.combo, 1)
        row.addWidget(self.next_button)

    def set_entries(self, entries: list[dict]) -> None:
        current = self.current_number()
        ordered = sorted(entries, key=lambda e: e["number"], reverse=True)
        self._numbers = sorted(e["number"] for e in entries)
        self.combo.blockSignals(True)
        self.combo.clear()
        seen: set[str] = set()
        for entry in ordered:
            batch = entry.get("batch_id")
            if batch and batch not in seen:
                seen.add(batch)
                self.combo.addItem(f"── batch {batch} ──")
                item = self.combo.model().item(self.combo.count() - 1)
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.combo.addItem(label_for(entry), entry["number"])
        self.combo.blockSignals(False)
        if current is not None:
            self.select_number(current)

    def current_number(self) -> int | None:
        return self.combo.currentData() if self.combo.count() else None

    def select_number(self, number: int) -> bool:
        index = self.combo.findData(number)
        if index < 0:
            return False
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        return True

    def _on_activated(self, index: int) -> None:
        number = self.combo.itemData(index)
        if number is not None:
            self.run_selected.emit(number)

    def _step(self, delta: int) -> None:
        current = self.current_number()
        if not self._numbers:
            return
        if current is None:
            target = self._numbers[-1]
        else:
            i = max(0, min(len(self._numbers) - 1, self._numbers.index(current) + delta))
            target = self._numbers[i]
        self.select_number(target)
        self.run_selected.emit(target)
