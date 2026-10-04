"""tool/ui/tabs/mechanisms.py -- tab 9: the mechanism library (docs/REDESIGN_PLAN.md section 3.3), read-only: for each
mechanism its cue, the sensory neurons it may excite, the input tier (feature-level or receptor), the evidence, its
origin and whether it exists yet. Below the table, the Sense settings (docs/SPEC_phase3.md): which object kinds are pursued
and how strong the home landmark is. They change what the senses pick up, never what the fly does. No builder until a later phase.
"""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFormLayout, QGroupBox, QLabel, QTableWidget, QTableWidgetItem,
                               QTextEdit, QVBoxLayout, QWidget)

from brain import calibration as C
from brain.library import EXPERIMENTS, MECHANISMS
from brain.settings import PURSUABLE_KINDS, SenseSettings
from tool.core.brain_runner import load_sense_settings, save_sense_settings
from tool.ui.widgets.no_scroll_inputs import NoScrollDoubleSpinBox
from tool.ui.widgets.scroll_page import install_scroll_page

KIND_LABELS = {"goomba": "Goomba (not pursued by default)", "koopa": "Koopa", "enemy": "other enemy",
               "powerup": "mushroom / other collectibles (power-ups)"}

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
        layout.addWidget(self._build_settings_box())
        layout.addStretch(1)
        self.table.selectRow(0)

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return MECHANISMS[rows[0].row()] if rows else None

    def _on_selected(self) -> None:
        m = self.selected()
        if m is not None:
            self.detail.setHtml(f"<h3>{m.name}</h3>" + mechanism_html(m))

    # ---- sense settings (docs/SPEC_phase3.md sections 4 and 6) --------------------------------------------------------
    def _build_settings_box(self) -> QGroupBox:
        box = QGroupBox("Sense settings (what the senses pick up; they never choose an action)")
        form = QFormLayout(box)
        saved = load_sense_settings(self._window.project.name)
        self.kind_checks = {}
        for kind in PURSUABLE_KINDS:
            cb = QCheckBox(KIND_LABELS[kind])
            cb.setChecked(kind in saved.pursuit_kinds)
            cb.toggled.connect(self._save_settings)
            self.kind_checks[kind] = cb
            form.addRow(cb)
        form.addRow(QLabel("Pursuit (LC10a): the fly turns toward the checked kinds when they are small and moving on screen "
                           "(Ribeiro 2018; Hindmarsh Sten 2021). It applies in the experiments that list pursuit (E3)."))
        self.landmark_spin = NoScrollDoubleSpinBox()
        self.landmark_spin.setRange(0.0, 100.0)
        self.landmark_spin.setDecimals(1)
        self.landmark_spin.setSingleStep(0.5)
        self.landmark_spin.setValue(saved.goal_cue_salience)
        self.landmark_spin.valueChanged.connect(self._save_settings)
        form.addRow(f"Home landmark strength (GOAL_CUE_SALIENCE, invented; default {C.GOAL_CUE_SALIENCE:g}; 0 = off)", self.landmark_spin)
        form.addRow(QLabel("Home landmark: a persistent cue on the right, a world property. It moves the 'go right' assumption to "
                           "the senses; it does not remove it. The shuffled arms get the same cue. It applies in E0."))
        self.arousal_spin = NoScrollDoubleSpinBox()
        self.arousal_spin.setRange(0.0, 1.0)
        self.arousal_spin.setDecimals(2)
        self.arousal_spin.setSingleStep(0.05)
        self.arousal_spin.setValue(saved.pursuit_arousal)
        self.arousal_spin.valueChanged.connect(self._save_settings)
        form.addRow(f"Fly arousal (PURSUIT_AROUSAL, invented; default {C.PURSUIT_AROUSAL:g}; range 0-1)", self.arousal_spin)
        form.addRow(QLabel("Arousal is a fly-state INPUT that scales how strongly pursuit drives LC10a (locomotion state raises visual "
                           "gain, Chiappe 2010; Maimon 2010). It is set here, constant over a run, and never read from the fly's own "
                           "output. Default: midpoint of the range where a synthetic dot is steered toward correctly and a static dot "
                           "gives nothing."))
        return box

    def settings(self) -> SenseSettings:
        return SenseSettings(tuple(k for k, cb in self.kind_checks.items() if cb.isChecked()), float(self.landmark_spin.value()),
                             float(self.arousal_spin.value()))

    def _save_settings(self, *_args) -> None:
        save_sense_settings(self._window.project.name, self.settings())
