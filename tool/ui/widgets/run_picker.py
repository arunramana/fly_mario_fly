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
    training = entry.get("training")
    if training:
        max_x = summary.get("max_x_abs", training.get("max_x"))
        max_x = f"{max_x:.0f}" if isinstance(max_x, (int, float)) else "?"
        if training.get("flag"):
            outcome = "flag"
        elif training.get("died"):
            outcome = "died"
        head = "baseline" if training["network"] == "baseline" else f"ep {training['episode']}"
        frames = "" if summary.get("raw_frames_path") else " · telemetry only"
        return f"#{entry['number']} · {head} · x {max_x} · {outcome}{frames}"
    fitness = entry.get("fitness")
    fit = f"{fitness:.0f}" if isinstance(fitness, (int, float)) else "--"
    max_x = summary.get("max_x_abs")
    max_x = f"{max_x:.0f}" if isinstance(max_x, (int, float)) else "?"
    return f"#{entry['number']} · seed {entry.get('seed', '?')} · x {max_x} · fit {fit} · {outcome}"


def _is_training_group(entry: dict) -> bool:
    return str(entry.get("group", "")).startswith("Training")


def _group_key(group: str):
    """"Training · real" first, then "Training · shuffled 1", 2, ... in order."""
    tail = group.rsplit(" ", 1)[-1]
    return (0, 0) if group.endswith("real") else (1, int(tail) if tail.isdigit() else 0)


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
        # Plain runs and the training baseline first (newest first), then
        # each "Training · ..." group under its own header.
        groups = sorted({e["group"] for e in ordered if _is_training_group(e)}, key=_group_key)
        for entry in [e for e in ordered if not _is_training_group(e)]:
            batch = entry.get("batch_id")
            if batch and batch not in seen:
                seen.add(batch)
                self._add_header(f"── batch {batch} ──")
            self.combo.addItem(label_for(entry), entry["number"])
        for group in groups:
            self._add_header(f"── {group} ──")
            for entry in ordered:
                if entry.get("group") == group:
                    self.combo.addItem(label_for(entry), entry["number"])
        self.combo.blockSignals(False)
        if current is not None:
            self.select_number(current)

    def _add_header(self, text: str) -> None:
        self.combo.addItem(text)
        item = self.combo.model().item(self.combo.count() - 1)
        item.setFlags(Qt.ItemFlag.NoItemFlags)

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
