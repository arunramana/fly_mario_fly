"""tool/ui/widgets/run_detail_panels.py -- Run tab / player redesign:
Config (the run's settings compared with the defaults), now the Config
overlay's content (tool/ui/widgets/run_edge_panel.py) rather than a fixed
right-hand drawer. The old DataPanel (a full text dump of the frame row
plus run summary) is gone -- tool/ui/widgets/run_data_overlay.py's
compact "see-through readout" replaces it, per the redesign's own ask.
Plain read-only text -- there is nothing here a user edits; a FINISHED
run's own recorded settings are history, not a live control.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import QTextEdit


class ConfigDiffPanel(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.set_config(None)

    def set_config(self, config) -> None:
        if config is None:
            self.setHtml("(no run selected)")
            return
        default = config.__class__()
        diffs = _diff_dataclass(config, default)
        if not diffs:
            self.setHtml("<i>Every scalar matched the shipped defaults.</i>")
            return
        lines = [f"{path}: <b>{value}</b> (default {default_value})" for path, value, default_value in diffs]
        self.setHtml("<br>".join(lines))


def _diff_dataclass(obj, default, prefix: str = "") -> list[tuple[str, object, object]]:
    diffs: list[tuple[str, object, object]] = []
    for f in dataclasses.fields(obj):
        value = getattr(obj, f.name)
        default_value = getattr(default, f.name)
        path = f"{prefix}{f.name}"
        if dataclasses.is_dataclass(value):
            diffs.extend(_diff_dataclass(value, default_value, prefix=f"{path}."))
        elif value != default_value:
            diffs.append((path, value, default_value))
    return diffs
