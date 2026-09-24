"""tool/ui/tabs/objects.py -- tab 3: power-ups, ? blocks, used blocks,
pipes/solids, pits/gaps. Not wired (C8, tool/PLAN.md P6, same as tab 2).
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ObjectsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(
            "Not wired yet.\n\n"
            "Per-kind object odour (power-ups, ? blocks, used blocks, "
            "pipes/solids, pits/gaps) is C8 (tool/PLAN.md P6), the same "
            "science sprint as tab 2. Today mushroom_odor/question_block_odor "
            "(bridge/perception.py) already read these from RAM/tile data; "
            "only per-kind tuning is missing."
        )
        label.setWordWrap(True)
        label.setEnabled(False)
        layout.addWidget(label)
        layout.addStretch(1)
