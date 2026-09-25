"""tool/ui/widgets/run_detail_panels.py -- ease-of-use redesign, Run tab
right-hand drawers: Data (the current frame's telemetry row plus the run
summary) and Config (the run's settings compared with the defaults).
Plain read-only text panels -- there is nothing here a user edits; a
FINISHED run's own recorded settings are history, not a live control.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import QTextEdit


class DataPanel(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.set_content(None, None)

    def set_content(self, row, summary: dict | None) -> None:
        lines = ["<b>Run summary</b>"]
        if summary:
            for key in sorted(summary):
                if key == "mb_weights":
                    continue
                lines.append(f"{key} = {summary[key]}")
        else:
            lines.append("(no run selected)")

        lines.append("<br><b>Current frame</b>")
        if row is not None:
            for key, value in row.items():
                lines.append(f"{key} = {value}")
        else:
            lines.append("(no frame)")
        self.setHtml("<br>".join(str(line) for line in lines))


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
