"""tool/ui/tabs/mechanisms.py -- tab 9: the mechanism library (docs/REDESIGN_PLAN.md section 3.3), read-only: for each
mechanism its cue, the sensory neurons it may excite, the input tier (feature-level or receptor), the evidence, its
origin and whether it exists yet. No switches or sliders until the guarded builder (a later phase).
"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget

from brain.library import EXPERIMENTS, MECHANISMS
from tool.ui.widgets.scroll_page import install_scroll_page

COLUMNS = ("Mechanism", "Entry neurons", "Input tier", "Status")


def mechanism_html(m) -> str:
    used = [e.id for e in EXPERIMENTS if m.id in e.mechanisms]
    rows = [("Cue", m.cue), ("Entry neurons (only these may be excited)", m.entry_neurons), ("Input tier", m.entry_tier),
            ("Evidence", m.evidence), ("Origin", m.origin), ("Status", m.status),
            ("Used by experiments", ", ".join(used) or "none yet")]
    if m.note:
        rows.append(("Note", m.note))
    return "<br>".join(f"<b>{k}:</b> {v}" for k, v in rows)


class MechanismsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        content = QWidget()
        layout = QVBoxLayout(content)
        install_scroll_page(self, content)
        layout.addWidget(QLabel("Mechanism library (read-only). Feature-level means the stimulus enters at early feature "
                                "neurons with published tuning (decision D1), not at photoreceptors."))
        self.table = QTableWidget(len(MECHANISMS), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        for r, m in enumerate(MECHANISMS):
            for c, text in enumerate((m.name, m.entry_neurons, m.entry_tier, m.status)):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.setFixedHeight(self.table.horizontalHeader().height() + self.table.verticalHeader().defaultSectionSize() * 9 + 4)
        self.table.itemSelectionChanged.connect(self._on_selected)
        layout.addWidget(self.table)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(220)
        layout.addWidget(self.detail)
        layout.addStretch(1)
        self.table.selectRow(0)

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return MECHANISMS[rows[0].row()] if rows else None

    def _on_selected(self) -> None:
        m = self.selected()
        if m is not None:
            self.detail.setHtml(f"<h3>{m.name}</h3>" + mechanism_html(m))
