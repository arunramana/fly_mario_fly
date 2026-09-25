"""tool/ui/widgets/run_playlist.py -- Run tab / player redesign: switching
runs. A panel that slides in from the right edge of the player, one
thumbnail per run (its death or last recorded frame), grouped by batch,
plus prev/next. Replaces the old sortable run table drawer.
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

THUMB_SIZE = (96, 90)
PANEL_WIDTH = 260


class RunPlaylist(QWidget):
    run_selected = Signal(int)  # run number

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(PANEL_WIDTH)
        self._entries: list[dict] = []
        self._numbers: list[int] = []
        self._current_number: int | None = None
        self._animation: QPropertyAnimation | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        nav = QHBoxLayout()
        self.prev_button = QPushButton("< Prev")
        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.next_button = QPushButton("Next >")
        self.next_button.clicked.connect(lambda: self._step(1))
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        layout.addLayout(nav)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QPixmap(*THUMB_SIZE).size())
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, 1)

    # ---- data -----------------------------------------------------------

    def set_entries(self, entries: list[dict]) -> None:
        """Newest first, like the run history everywhere else -- batch
        siblings (same batch_id) are kept adjacent with a small group
        label the first time a new batch_id is seen."""
        self._entries = list(reversed(entries))
        self._numbers = [e["number"] for e in self._entries]
        self.list_widget.clear()
        seen_batches: set[str] = set()
        for entry in self._entries:
            batch_id = entry.get("batch_id")
            if batch_id and batch_id not in seen_batches:
                seen_batches.add(batch_id)
                header = QListWidgetItem(f"-- batch {batch_id} --")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list_widget.addItem(header)
            item = QListWidgetItem(_label_for(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry["number"])
            item.setIcon(_thumbnail_for(entry))
            self.list_widget.addItem(item)
        self._select_row_for_number(self._current_number)

    def select_number(self, number: int) -> bool:
        if number not in self._numbers:
            return False
        self._current_number = number
        self._select_row_for_number(number)
        return True

    def _select_row_for_number(self, number: int | None) -> None:
        if number is None:
            return
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == number:
                self.list_widget.setCurrentItem(item)
                return

    def _step(self, delta: int) -> None:
        if not self._numbers:
            return
        if self._current_number is None:
            new_index = 0
        else:
            index = self._numbers.index(self._current_number)
            new_index = max(0, min(len(self._numbers) - 1, index + delta))
        number = self._numbers[new_index]
        self._current_number = number
        self._select_row_for_number(number)
        self.run_selected.emit(number)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        number = item.data(Qt.ItemDataRole.UserRole)
        if number is None:
            return
        self._current_number = number
        self.run_selected.emit(number)

    # ---- slide in/out -----------------------------------------------------

    def slide_in(self, anchor_width: int) -> None:
        self.setVisible(True)
        self._animate_to(anchor_width - self.width())

    def slide_out(self, anchor_width: int) -> None:
        self._animate_to(anchor_width, on_finished=lambda: self.setVisible(False))

    def _animate_to(self, x: int, on_finished=None) -> None:
        if self._animation is not None:
            self._animation.stop()
        target = QRect(x, self.y(), self.width(), self.height())
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setDuration(200)
        self._animation.setEndValue(target)
        if on_finished is not None:
            self._animation.finished.connect(on_finished)
        self._animation.start()


def _label_for(entry: dict) -> str:
    summary = entry.get("summary", {})
    if summary.get("cancelled"):
        badge = "CANCELLED"
    elif summary.get("died_or_flagged") and summary.get("flag_get"):
        badge = "FLAG"
    elif summary.get("died_or_flagged"):
        badge = "DIED"
    else:
        badge = "SURVIVED"
    max_x = summary.get("max_x_abs", "?")
    fitness = entry.get("fitness")
    fitness_str = f"{fitness:.0f}" if isinstance(fitness, (int, float)) else "?"
    return f"#{entry['number']:03d}  [{badge}]\nmax_x={max_x}  fitness={fitness_str}"


def _thumbnail_for(entry: dict) -> QPixmap:
    from pathlib import Path
    from tool.core.frame_store import frames_to_rgb, load_frames
    from tool.ui.widgets.preview import frame_to_pixmap

    raw_path = entry.get("summary", {}).get("raw_frames_path")
    if raw_path and Path(raw_path).exists():
        loaded = load_frames(raw_path)
        if loaded is not None:
            frames, palette = loaded
            rgb = frames_to_rgb(frames[-1], palette)
            pixmap = frame_to_pixmap(rgb)
            return pixmap.scaled(*THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.FastTransformation)
    placeholder = QPixmap(*THUMB_SIZE)
    placeholder.fill(Qt.GlobalColor.darkGray)
    return placeholder
