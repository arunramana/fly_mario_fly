"""tool/ui/widgets/param_form.py -- auto-built form from schema.py's
ControlSpecs: one row per scalar, grouped by circuit, spinboxes with
range clamps, provenance tooltips, greyed if not `live` (tool/PLAN.md P3,
ground rule 4 -- "no control lies").
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from tool.core.schema import all_controls, get_value, with_value
from tool.ui.widgets.no_scroll_inputs import (
    NoScrollDoubleSpinBox, NoScrollSlider, NoScrollSpinBox, ScientificDoubleSpinBox,
)

FIELD_MAX_WIDTH = 130  # ease-of-use redesign: a compact field column, not a full-width row
SLIDER_SCALE = 10_000  # ranged fields' slider resolution (matches their own 4+ decimal display)

# Below this magnitude, fixed-decimal display either rounds to a lying
# "0.00" or needs dozens of unreadable decimal places -- scientific
# notation instead (e.g. network.denormal_flush_threshold = 1e-30).
SCIENTIFIC_THRESHOLD = 1e-4


def _decimals_for(value: float, has_range: bool) -> int:
    """Most floats get 2-4 decimals -- readable, not a wall of digits
    (ease-of-use redesign). A handful of real config/params.py values
    (odour.alpha_adapt = 1/90, mbon_dna02_frac_l/r) need more than 4 or
    they'd silently round to a different, wrong-looking number -- ground
    rule 4, and tool/tests/test_param_form.py's own 1e-9 round-trip
    tolerance. Search upward only as far as each field actually needs,
    instead of the old universal 10 decimals for every field regardless.
    Anything below SCIENTIFIC_THRESHOLD uses ScientificDoubleSpinBox
    instead of this function. Ranged fields also drive a slider (below);
    they start the search at 4 decimals so the slider's own resolution
    stays meaningful across a typically narrow measured band (e.g.
    noise.sigma's 0.04-0.06)."""
    candidates = (4, 6, 8, 10) if has_range else (2, 3, 4, 6, 8, 10)
    for d in candidates:
        if abs(round(value, d) - value) < 1e-9:
            return d
    return 10


class ParamForm(QWidget):
    """Emits `changed(config)` with a NEW ProjectConfig whenever a control
    is edited (ProjectConfig is frozen -- every edit replaces it, never
    mutates it)."""

    changed = Signal(object)

    def __init__(self, config, parent=None, groups: set[str] | None = None, scrollable: bool = True):
        """`groups=None` (default): every scalar, the original scrollable
        stack of everything ALL_PARAM_CLASSES tracks. `groups={"jump",
        "dnp02"}`: only those groups' own fields -- tool/SPEC_ui_retro.md
        section 8's per-circuit-card detail panel, reached through a card
        instead of a scrollable stack of all of them at once.
        `scrollable=False`: no scroll area of its own -- the form sits in a page that
        already scrolls (the Circuits tab), so the wheel never gets trapped in a nested one."""
        super().__init__(parent)
        self._config = config
        self._groups = groups
        self._widget_by_path: dict[str, QWidget] = {}
        self._group_boxes: dict[str, QGroupBox] = {}
        self._slider_by_path: dict[str, QSlider] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
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
            # A narrow window puts the label above its field instead of clipping the label.
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
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
        if scrollable:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(inner)
            outer.addWidget(scroll)
        else:
            outer.addWidget(inner)

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
            widget.setEnabled(control.wiring == "live")
            if control.wiring != "live":
                widget.setToolTip(f"not wired yet ({control.wiring})")
            self._widget_by_path[control.path] = widget
            return widget

        if control.type is int:
            spin = NoScrollSpinBox()
            # control.range is a MEASURED-ROBUST-BAND hint, not a hard
            # limit -- Qt's own setRange() clamps setValue() to fit, which
            # silently displayed a config value outside the band as the
            # nearest bound (noise.sigma=0.0 showed as 0.04, its range's
            # own lower edge). The spin box's real range is always wide;
            # the measured band is advisory only, shown in the tooltip.
            spin.setRange(-2_000_000_000, 2_000_000_000)
            spin.setValue(int(get_value(self._config, control.path)))
            spin.valueChanged.connect(lambda v, p=control.path: self._on_change(p, v))
        else:
            value = float(get_value(self._config, control.path))
            if value != 0 and abs(value) < SCIENTIFIC_THRESHOLD:
                spin = ScientificDoubleSpinBox()
            else:
                spin = NoScrollDoubleSpinBox()
                spin.setDecimals(_decimals_for(value, control.range is not None))
            spin.setRange(-1e9, 1e9)
            spin.setSingleStep(0.01)
            spin.setValue(value)
            spin.valueChanged.connect(lambda v, p=control.path: self._on_change(p, v))

        spin.setMaximumWidth(FIELD_MAX_WIDTH)
        spin.setEnabled(control.wiring == "live")
        if control.wiring != "live":
            spin.setToolTip(f"not wired yet ({control.wiring})")
        self._widget_by_path[control.path] = spin

        if control.range is None:
            return spin

        # Ease-of-use redesign: a field with a real measured/robust band
        # (only 3 of 60 scalars today) also gets a slider next to it,
        # scrubbing across exactly that band. The spin box stays the one
        # writable path -- the slider only ever calls spin.setValue(),
        # which is what actually reaches _on_change() -- so there is
        # still exactly one place that writes this scalar (section 3's
        # "one home per setting" rule, unaffected by adding a second
        # WAY to reach the same box).
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(spin)

        lo, hi = control.range
        slider = NoScrollSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(lo * SLIDER_SCALE), int(hi * SLIDER_SCALE))
        slider.setValue(int(max(lo, min(hi, spin.value())) * SLIDER_SCALE))
        slider.setEnabled(control.wiring == "live")
        slider.setToolTip(f"measured band: {lo}-{hi}")

        def _slider_moved(raw: int, s=spin, scale=SLIDER_SCALE) -> None:
            s.setValue(raw / scale)

        def _spin_changed(value: float, sl=slider, scale=SLIDER_SCALE, lo=lo, hi=hi) -> None:
            sl.blockSignals(True)
            sl.setValue(int(max(lo, min(hi, value)) * scale))
            sl.blockSignals(False)

        slider.valueChanged.connect(_slider_moved)
        spin.valueChanged.connect(_spin_changed)
        row.addWidget(slider, 1)
        self._slider_by_path[control.path] = slider
        return container

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
            # widget's own signal was just blocked, so the slider's usual
            # sync via spin.valueChanged (_spin_changed) never fired --
            # resync it directly rather than leave it showing a stale
            # position after loading a different project/config.
            slider = self._slider_by_path.get(control.path)
            if slider is not None:
                lo, hi = control.range
                slider.blockSignals(True)
                slider.setValue(int(max(lo, min(hi, value)) * SLIDER_SCALE))
                slider.blockSignals(False)
