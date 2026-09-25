"""tool/ui/widgets/run_table.py -- ease-of-use redesign: a sortable table
of every recorded run (#, seed, frames, max_x, fitness, died, cancelled,
time), replacing the old plain history QListWidget. Selecting a row is
the one way to load an older run's plots/video into the detail pane next
to it (tool/ui/tabs/run.py).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from tool.core.fitness import fitness_of
from tool.core.tool_settings import FitnessSettings

COLUMNS = ["#", "seed", "frames", "max_x", "fitness", "died", "cancelled", "batch", "time"]


class _SortableItem(QTableWidgetItem):
    """Compares by the underlying value (int/float/bool/str), not the
    display text -- so "#10" sorts after "#9", not before it."""

    def __init__(self, value, text: str | None = None):
        super().__init__(text if text is not None else ("" if value is None else str(value)))
        self._value = value

    def __lt__(self, other):
        v1 = self._value
        v2 = getattr(other, "_value", None)
        if v1 is None:
            return True
        if v2 is None:
            return False
        try:
            return v1 < v2
        except TypeError:
            return str(v1) < str(v2)


def _entry_fitness(entry: dict) -> float | None:
    summary = entry.get("summary", {})
    if summary.get("cancelled"):
        return None
    try:
        fitness_settings = FitnessSettings(**entry["run_spec"]["tool_settings"]["fitness"])
    except (KeyError, TypeError):
        return None
    try:
        return fitness_of(fitness_settings, summary)
    except (KeyError, TypeError):
        return None


class RunTable(QTableWidget):
    row_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        # Ease-of-use redesign: narrow columns sized to their own short
        # content (#, seed, frames...) instead of Qt's default equal-ish
        # split, which pushed the table into a horizontal scrollbar even
        # with generous splitter width.
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_entries(self, entries: list[dict]) -> None:
        """`entries`: tool.core.run_store.list_runs()'s own list, oldest
        first -- shown newest-first by default via an initial sort on #,
        but the whole point of a real table is the user can re-sort by
        any column (fitness, max_x, ...) instead."""
        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for entry in entries:
            self._add_row(entry)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.DescendingOrder)  # newest run first, by default

    def _add_row(self, entry: dict) -> None:
        row = self.rowCount()
        self.insertRow(row)
        summary = entry.get("summary", {})
        fitness = _entry_fitness(entry)
        batch_id = entry.get("batch_id")
        values = [
            entry.get("number"),
            entry.get("seed"),
            summary.get("n_frames"),
            summary.get("max_x_abs"),
            fitness,
            summary.get("died_or_flagged"),
            bool(summary.get("cancelled")),
            batch_id or "",
            entry.get("time", ""),
        ]
        texts = [
            f"#{values[0]:03d}" if values[0] is not None else "",
            str(values[1]) if values[1] is not None else "",
            str(values[2]) if values[2] is not None else "",
            f"{values[3]:.1f}" if values[3] is not None else "",
            f"{values[4]:.1f}" if values[4] is not None else "",
            str(values[5]) if values[5] is not None else "",
            "yes" if values[6] else "",
            batch_id or "",
            str(values[8])[:19].replace("T", " "),  # ISO datetime, trimmed to seconds
        ]
        for col, (value, text) in enumerate(zip(values, texts)):
            item = _SortableItem(value, text)
            self.setItem(row, col, item)
        self.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry)

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        entry = self.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self.row_selected.emit(entry)

    def selected_number(self) -> int | None:
        items = self.selectedItems()
        if not items:
            return None
        entry = self.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return entry.get("number") if entry else None

    def select_number(self, number: int) -> bool:
        """Selects the row for run `number`, wherever the current sort
        put it -- returns False (no-op) if that run isn't in the table."""
        for row in range(self.rowCount()):
            entry = self.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if entry and entry.get("number") == number:
                self.selectRow(row)
                return True
        return False

    def select_adjacent(self, delta: int) -> None:
        """Prev/next run buttons: steps by VISUAL row (whatever the
        current sort/column order is), not by run number -- "next" means
        "the next one in this table," matching what the user is actually
        looking at."""
        items = self.selectedItems()
        current_row = items[0].row() if items else -1
        target = current_row + delta
        if 0 <= target < self.rowCount():
            self.selectRow(target)
