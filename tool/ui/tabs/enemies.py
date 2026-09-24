"""tool/ui/tabs/enemies.py -- tab 2: per-entity odour channel, valence,
looming salience, danger weight. Not wired (C8, tool/PLAN.md P6 -- a
science sprint of its own, needs docs/SPEC_entity_perception.md first).
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EnemiesTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(
            "Not wired yet.\n\n"
            "Per-kind odour channel / valence / looming salience / danger "
            "weight is C8 (tool/PLAN.md P6) -- a science sprint with its own "
            "docs/SPEC_entity_perception.md, not tool plumbing. Today every "
            "enemy (Goomba, Koopa, generic) shares one aggregate odour "
            "channel (bridge/perception.py)."
        )
        label.setWordWrap(True)
        label.setEnabled(False)
        layout.addWidget(label)
        layout.addStretch(1)
