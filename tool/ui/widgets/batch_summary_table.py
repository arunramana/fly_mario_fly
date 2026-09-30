"""tool/ui/widgets/batch_summary_table.py -- a small table for one batch:
seed | max_x | flag | frames | stomps | escape jumps, with "wins: N / M" and the mean
max_x underneath. Hidden while there is no batch to show."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from tool.core.batch_summary import BATCH_COLUMNS, batch_rows, batch_stats


class BatchSummaryTable(QWidget):
    MAX_VISIBLE_ROWS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(BATCH_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(BATCH_COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.totals_label = QLabel("")
        layout.addWidget(self.table)
        layout.addWidget(self.totals_label)
        self.setVisible(False)

    def set_entries(self, batch_entries: list[dict]) -> None:
        """`batch_entries`: the run-store entries of ONE batch (empty hides the table)."""
        rows = batch_rows(batch_entries)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                text = ("yes" if value else "no") if c == 2 else ("" if value is None else str(value))
                self.table.setItem(r, c, QTableWidgetItem(text))
        visible = min(len(rows), self.MAX_VISIBLE_ROWS)
        row_h = self.table.verticalHeader().defaultSectionSize()   # follows font + DPI, not 24px
        self.table.setFixedHeight(self.table.horizontalHeader().height() + row_h * visible + 4)
        if rows:
            wins, n, mean_x = batch_stats(rows)
            mean = "?" if mean_x is None else f"{mean_x:.0f}"
            from tool.core.evaluation import wilson_ci
            lo, hi = wilson_ci(wins, n)
            self.totals_label.setText(f"wins: {wins} / {n} (95% CI {100 * lo:.0f}-{100 * hi:.0f}%)    mean max_x: {mean}")
        self.setVisible(bool(rows))
