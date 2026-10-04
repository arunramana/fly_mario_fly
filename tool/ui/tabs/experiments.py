"""tool/ui/tabs/experiments.py -- tab 8: the experiment ladder (docs/REDESIGN_PLAN.md section 4) as a read-only library
with provenance, plus Run buttons for the experiments that can run today (E0, E1, E3). A run is played in tab 7 (Watch); the
real-vs-shuffled evaluation and its results are on tab 10. Nothing here is an input to the brain.
"""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from brain.e1 import E1_SEED0   # noqa: F401  (held-out eval seeds, deliberately NOT the Run default)
from brain.library import EXPERIMENTS, mechanism
from tool.ui.widgets.no_scroll_inputs import NoScrollSpinBox
from tool.ui.widgets.scroll_page import install_scroll_page

RUN_DEFAULT_SEED = 9100          # development seed for single runs; 3000-3019 are held out for the evaluation on tab 10
COLUMNS = ("ID", "Experiment", "Scene", "Mechanisms on", "Status")


def provenance_html(entry) -> str:
    rows = [("Scene", entry.scene), ("Pass criterion", entry.criterion), ("Controls", entry.controls),
            ("Origin", entry.origin), ("Status", entry.status)]
    html = "<br>".join(f"<b>{k}:</b> {v}" for k, v in rows) + "<br><br><b>Mechanisms on (with their input tier):</b>"
    for mid in entry.mechanisms:
        m = mechanism(mid)
        html += f"<br>- <b>{m.name}</b> [{m.status}]: enters at {m.entry_neurons} ({m.entry_tier}); evidence: {m.evidence}"
    return html


class ExperimentsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        content = QWidget()
        layout = QVBoxLayout(content)
        install_scroll_page(self, content)
        layout.addWidget(QLabel("Experiment library (read-only). Stimuli enter only at sensory neurons; nothing here is a brain input."))

        self.table = QTableWidget(len(EXPERIMENTS), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        for r, e in enumerate(EXPERIMENTS):
            for c, text in enumerate((e.id, e.name, e.scene, ", ".join(mechanism(m).name for m in e.mechanisms), e.status)):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.setFixedHeight(self.table.horizontalHeader().height() + self.table.verticalHeader().defaultSectionSize() * 8 + 4)
        self.table.itemSelectionChanged.connect(self._on_selected)
        layout.addWidget(self.table)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(180)
        layout.addWidget(self.detail)

        box = QGroupBox("Run (experiments marked runnable)")
        form = QFormLayout(box)
        self.seed_spin = NoScrollSpinBox()
        self.seed_spin.setRange(0, 99999)
        self.seed_spin.setValue(RUN_DEFAULT_SEED)
        form.addRow("Brain noise seed", self.seed_spin)
        self.shuffle_spin = NoScrollSpinBox()
        self.shuffle_spin.setRange(1, 99999)
        self.shuffle_spin.setValue(1)
        form.addRow("Shuffle seed (shuffled run)", self.shuffle_spin)
        buttons = QHBoxLayout()
        self.class_check = QCheckBox("class-preserving shuffle (for the shuffled run; default is degree-preserving)")
        form.addRow(self.class_check)
        self.run_real_button = QPushButton("Run E1 -- real connectome")
        self.run_shuffled_button = QPushButton("Run E1 -- shuffled connectome")
        self.run_real_button.clicked.connect(lambda: self._run(False))
        self.run_shuffled_button.clicked.connect(lambda: self._run(True))
        buttons.addWidget(self.run_real_button)
        buttons.addWidget(self.run_shuffled_button)
        form.addRow(buttons)
        self.run_note = QLabel("The run plays in tab 7 (Run) with the brain map; the 20-seed real-vs-shuffled evaluation is on tab 10 (Results). "
                               "Pursuit and the home landmark use the settings on tab 9 (Mechanisms), but only in the experiments that list them.")
        self.run_note.setWordWrap(True)
        form.addRow(self.run_note)
        layout.addWidget(box)
        layout.addStretch(1)
        self.table.selectRow(1)          # E1: the one that runs today

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return EXPERIMENTS[rows[0].row()] if rows else None

    def _on_selected(self) -> None:
        e = self.selected()
        if e is None:
            return
        self.detail.setHtml(f"<h3>{e.id} -- {e.name}</h3>" + provenance_html(e))
        runnable = e.status == "runnable"
        self.run_real_button.setText(f"Run {e.id} -- real connectome")
        self.run_shuffled_button.setText(f"Run {e.id} -- shuffled connectome")
        for b in (self.run_real_button, self.run_shuffled_button):
            b.setEnabled(runnable)

    def _run(self, shuffled: bool) -> None:
        e = self.selected()
        self._window.brain_runs.start_run(self.seed_spin.value(), shuffled, self.shuffle_spin.value(),
                                          e.id if e is not None and e.status == "runnable" else "E1", self.class_check.isChecked())
