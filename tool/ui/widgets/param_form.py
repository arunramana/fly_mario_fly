"""tool/ui/widgets/param_form.py -- auto-built form from schema.py's
ControlSpecs: one row per scalar, grouped by circuit, spinboxes with
range clamps, provenance tooltips, greyed if not `live` (tool/PLAN.md P3,
ground rule 4 -- "no control lies").
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from tool.core.schema import all_controls, get_value, with_value


class ParamForm(QWidget):
    """Emits `changed(config)` with a NEW ProjectConfig whenever a control
    is edited (ProjectConfig is frozen -- every edit replaces it, never
    mutates it)."""

    changed = Signal(object)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._widget_by_path: dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        groups: dict[str, list] = {}
        for control in all_controls():
            groups.setdefault(control.group, []).append(control)

        for group_name in sorted(groups):
            box = QGroupBox(group_name)
            form = QFormLayout(box)
            for control in groups[group_name]:
                widget = self._build_widget(control)
                label = QLabel(control.name)
                label.setToolTip(
                    f"{control.provenance}\nrange: {control.range}\nhome: {control.home}"
                )
                form.addRow(label, widget)
            inner_layout.addWidget(box)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _build_widget(self, control) -> QWidget:
        if control.type is bool:
            widget: QWidget = QCheckBox()
            widget.setChecked(bool(get_value(self._config, control.path)))
            widget.toggled.connect(lambda v, p=control.path: self._on_change(p, v))
        elif control.type is int:
            widget = QSpinBox()
            lo, hi = control.range or (-2_000_000_000, 2_000_000_000)
            widget.setRange(int(lo), int(hi))
            widget.setValue(int(get_value(self._config, control.path)))
            widget.valueChanged.connect(lambda v, p=control.path: self._on_change(p, v))
        else:
            widget = QDoubleSpinBox()
            lo, hi = control.range or (-1e9, 1e9)
            widget.setRange(float(lo), float(hi))
            widget.setDecimals(4)
            widget.setSingleStep(0.01)
            widget.setValue(float(get_value(self._config, control.path)))
            widget.valueChanged.connect(lambda v, p=control.path: self._on_change(p, v))

        widget.setEnabled(control.wiring == "live")
        if control.wiring != "live":
            widget.setToolTip(f"not wired yet ({control.wiring})")
        self._widget_by_path[control.path] = widget
        return widget

    def _on_change(self, path: str, value) -> None:
        self._config = with_value(self._config, path, value)
        self.changed.emit(self._config)

    def set_config(self, config) -> None:
        """Refreshes every widget from `config` without emitting `changed`
        -- for loading a project or an external reset, not user edits."""
        self._config = config
        for control in all_controls():
            widget = self._widget_by_path.get(control.path)
            if widget is None:
                continue
            widget.blockSignals(True)
            value = get_value(config, control.path)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            else:
                widget.setValue(value)
            widget.blockSignals(False)
