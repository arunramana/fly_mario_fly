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

    def __init__(self, config, parent=None, groups: set[str] | None = None):
        """`groups=None` (default): every scalar, the original scrollable
        stack of everything ALL_PARAM_CLASSES tracks. `groups={"jump",
        "dnp02"}`: only those groups' own fields -- tool/SPEC_ui_retro.md
        section 8's per-circuit-card detail panel, reached through a card
        instead of a scrollable stack of all of them at once."""
        super().__init__(parent)
        self._config = config
        self._groups = groups
        self._widget_by_path: dict[str, QWidget] = {}
        self._group_boxes: dict[str, QGroupBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        by_group: dict[str, list] = {}
        for control in all_controls():
            if self._groups is not None and control.group not in self._groups:
                continue
            by_group.setdefault(control.group, []).append(control)

        for group_name in sorted(by_group):
            box = QGroupBox(group_name)
            form = QFormLayout(box)
            for control in by_group[group_name]:
                widget = self._build_widget(control)
                label = QLabel(control.name)
                label.setToolTip(
                    f"{control.provenance}\nrange: {control.range}\nhome: {control.home}"
                )
                form.addRow(label, widget)
            inner_layout.addWidget(box)
            self._group_boxes[group_name] = box

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def show_only_groups(self, groups: set[str] | None) -> None:
        """Runtime visibility toggle over one full, eagerly-built form --
        tool/SPEC_ui_retro.md section 8: the Circuits tab keeps ONE
        ParamForm (so `_widget_by_path` still covers every scalar, the
        single writable home section 3 requires) and shows/hides each
        group's own box depending on which card is selected, rather than
        building a separate ParamForm per card. `groups=None` shows every
        group -- the original scrollable stack."""
        for group_name, box in self._group_boxes.items():
            box.setVisible(groups is None or group_name in groups)

    def _build_widget(self, control) -> QWidget:
        if control.type is bool:
            widget: QWidget = QCheckBox()
            widget.setChecked(bool(get_value(self._config, control.path)))
            widget.toggled.connect(lambda v, p=control.path: self._on_change(p, v))
        elif control.type is int:
            widget = QSpinBox()
            # control.range is a MEASURED-ROBUST-BAND hint, not a hard
            # limit -- Qt's own setRange() clamps setValue() to fit, which
            # silently displayed a config value outside the band as the
            # nearest bound (noise.sigma=0.0 showed as 0.04, its range's
            # own lower edge). The spin box's real range is always wide;
            # the measured band is advisory only, shown in the tooltip.
            widget.setRange(-2_000_000_000, 2_000_000_000)
            widget.setValue(int(get_value(self._config, control.path)))
            widget.valueChanged.connect(lambda v, p=control.path: self._on_change(p, v))
        else:
            widget = QDoubleSpinBox()
            widget.setRange(-1e9, 1e9)
            # 4 decimals silently truncated anything finer -- e.g.
            # odour.alpha_adapt (1/90 = 0.011111111111111112) displayed as
            # 0.0111, a different, wrong-looking number, not just a
            # rounded one. 10 is enough for every value this project
            # actually hand-sets (config/params.py's own docs/SCALARS.md);
            # QDoubleSpinBox is fundamentally decimal-rounding, so it
            # still can't be bit-exact for an arbitrary irrational-looking
            # double (see tool/tests/test_param_form.py's own tolerance).
            widget.setDecimals(10)
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
