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
import html

from PySide6.QtWidgets import QCheckBox, QTextEdit, QVBoxLayout, QWidget


class ConfigDiffPanel(QTextEdit):
    """The run's FULL saved config, grouped by section, values that differ
    from the shipped defaults highlighted; `changed_only` hides the rest."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._config = None
        self.changed_only = False
        self._render()

    def set_config(self, config) -> None:
        self._config = config
        self._render()

    def set_changed_only(self, changed_only: bool) -> None:
        self.changed_only = changed_only
        self._render()

    def _render(self) -> None:
        config = self._config
        if config is None:
            self.setHtml("(no run selected)")
            return
        default = config.__class__()
        diff_paths = {path for path, _v, _d in _diff_dataclass(config, default)}
        if self.changed_only and not diff_paths:
            self.setHtml("<i>Every scalar matched the shipped defaults.</i>")
            return
        lines = []
        for section in dataclasses.fields(config):
            value = getattr(config, section.name)
            rows = []
            if dataclasses.is_dataclass(value):
                for path, v, d in _flatten(value, getattr(default, section.name), section.name):
                    changed = path in diff_paths
                    if self.changed_only and not changed:
                        continue
                    rows.append(_row(path.split(".", 1)[1], v, d, changed))
            else:
                changed = section.name in diff_paths
                if not self.changed_only or changed:
                    rows.append(_row(section.name, value, getattr(default, section.name), changed))
            if rows:
                lines.append(f"<b>[{section.name}]</b>")
                lines.extend(rows)
        self.setHtml("<br>".join(lines))


class ConfigPanelContent(QWidget):
    """ConfigDiffPanel plus its 'changed only' toggle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = QCheckBox("changed only")
        self.panel = ConfigDiffPanel()
        self.toggle.toggled.connect(self.panel.set_changed_only)
        layout.addWidget(self.toggle)
        layout.addWidget(self.panel, 1)

    def set_config(self, config) -> None:
        self.panel.set_config(config)


def _row(name, value, default, changed) -> str:
    text = f"{html.escape(str(name))} = {html.escape(str(value))}"
    if changed:
        return (f"<span style='background-color:#c8a000;color:black'>&nbsp;{text}"
                f" (default {html.escape(str(default))})&nbsp;</span>")
    return text


def _flatten(obj, default, prefix):
    for f in dataclasses.fields(obj):
        v, d = getattr(obj, f.name), getattr(default, f.name)
        path = f"{prefix}.{f.name}"
        if dataclasses.is_dataclass(v):
            yield from _flatten(v, d, path)
        else:
            yield path, v, d


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
