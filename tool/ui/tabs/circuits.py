"""tool/ui/tabs/circuits.py -- tab 4: a card per circuit (jump/steering/
speed/takeoff/MDN/mushroom body), each showing a real brain-map image
(render.brain_panel.highlight_populations) plus a two-line description;
clicking a card reveals just that circuit's own config/params.py group(s)
in the (single, eagerly-built) ParamForm to its right (tool/SPEC_ui_retro.md
sections 8/10, ease-of-use redesign -- an inspector panel, not a
scrollable stack below the cards). Noise sigma + seed, and the shuffled-
connectome toggle (C5) stay above the grid -- cross-cutting, not part of
any one circuit. Presets for this tab live in the header's Presets menu
(main_window.py), not a per-tab bar.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QLabel, QScrollArea,
    QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from config.params import ArousalParams, GapAheadParams, MbonReadoutParams, Dnp01RefractoryParams, Dnp02RefractoryParams, MbSpatialInputParams, MotorDirectParams, PagePerceptionParams
from config.project_config import from_dict as config_from_dict
from tool.core.circuit_manifest import CIRCUIT_REGISTRY, OTHER_ENTRY
from tool.ui.widgets.card_button import make_card_button
from tool.ui.widgets.circuit_card_image import circuit_card_pixmap
from tool.ui.widgets.flow_layout import FlowLayout
from tool.ui.widgets.no_scroll_inputs import NoScrollSpinBox
from tool.ui.widgets.param_form import ParamForm

# (ModulesConfig field, params class, label, tooltip) -- a checkbox per
# controller module (bridge/controller_modules.py); checked = present in
# config.modules (with default params, edit them in config.json), unchecked =
# None. Legacy is read-only: main_window disables every tab for it.
MODULE_TOGGLES = [
    ("page_perception", PagePerceptionParams, "Page-aware looming (perception)",
     "Enemy distance uses the page byte, so a Goomba just across a 256px boundary is ahead, "
     "not ~230px behind. Changes what the fly sees, never an action."),
    ("gap_ahead", GapAheadParams, "Gap ahead (perception)",
     "Feeds the existing gap input from a few tiles away, scaled up as the edge approaches."),
    ("mb_spatial_inputs", MbSpatialInputParams, "MB spatial inputs (perception)",
     "Two extra Kenyon-cell inputs: closeness of the next pit edge and of the nearest enemy "
     "ahead (page-corrected), so learning can key on where danger is."),
    ("dnp02_refractory", Dnp02RefractoryParams, "DNp02 refractory period (circuit)",
     "An absolute refractory period on the DNp02 spiking cells. Without it the real "
     "DNp02 <-> pIP1 feedback loop latches on after one spike and DNp02 stays saturated "
     "all run (docs/RUNS.md, test3 run 9). Changes circuit dynamics when on."),
    ("dnp01_refractory", Dnp01RefractoryParams, "DNp01 refractory period (circuit)",
     "An absolute refractory period on the DNp01 (Giant Fiber) spiking cells, switched "
     "independently of the DNp02 one. Changes circuit dynamics when on."),
    ("arousal", ArousalParams, "Arousal (pC1)",
     "A steady drive into the pC1 arousal neurons, delivered through their real synapses "
     "(share of each target's total input) to DNp09, DNa01/02, MDN, pIP1 ... Set the level with "
     "the Character tab's Arousal slider. docs/SPEC_arousal_pc1.md"),
    ("motor_direct", MotorDirectParams, "MotorDirect (motor)",
     "A follows a leaky integral of the motor neurons' own activity instead of the fixed "
     "jump-hold / cooldown counters (docs/CONTROL_AUDIT.md rows 1-3)."),
    ("mbon_readout", MbonReadoutParams, "Per-MBON readout (mushroom body)",
     "Each MBON gets its own connectome-derived weight onto DNp01 / DLMn / DNp09 / MDN "
     "instead of one scalar mean, so learning acts on specific pathways."),
]

# Editable parameters per module: (param, kind, lo, hi, step, tooltip). Shown
# only while the module is on. Tooltips say what each value is compared with.
_REFRACTORY_TIP = (
    "Absolute refractory period of the spiking cells, in network substeps (10 per frame, so 10 = "
    "16.7 ms). Compared against how fast the downstream partner decays: pIP1 needs ~5 substeps "
    "to fall below the ~11 that still re-fires DNp02. {extra}")
MODULE_PARAM_UI: dict[str, list] = {
    "arousal": [
        ("arousal", "float", 0.0, 1.0, 0.05,
         "Arousal level, 0-1 (also the Character tab slider). pC1 activity = arousal x arousal_max_h. "
         "0 = no injection: the run is identical to one without the module."),
        ("arousal_max_h", "float", 0.0, 50.0, 1.0,
         "pC1 activity at arousal 1, in network h units. Compared against the network clip (50, the "
         "most a neuron can reach) and against typical driven activity: DNp09 sits near 1 at rest, so "
         "10 gives DNp09 about +0.3 (direct only)."),
        ("two_hop", "bool", 0, 1, 1,
         "Also drive through one intermediate neuron (pC1 -> X -> target, signed by X's transmitter). "
         "Off = direct pC1 synapses only. Roughly doubles the steering effect and lowers the Giant "
         "Fiber's response to looming; the intermediates' own dynamics are not simulated.")],
    "gap_ahead": [("perceive_tiles", "int", 1, 16, 1,
                   "How many tiles ahead the pit-edge input starts. Compared against the distance "
                   "to the nearest non-ground tile (tiles): inside this range the gap input is "
                   "width x (n - d + 1) / n, reaching today's full strength at the edge. The "
                   "current itself is still takeoff.gap_gain x that value.")],
    "motor_direct": [
        ("decay", "float", 0.0, 0.999, 0.01,
         "Per-frame multiplier on the motor drive (time constant = 1 / (1 - decay) frames; 0.9 = "
         "10). Compared against a_threshold: A stays down until the decaying drive falls below it."),
        ("a_threshold", "float", 0.01, 20.0, 0.05,
         "A is down while the DRIVE is at or above this. The drive is the leaky integral of TTMn's "
         "RISE (in units of jump.ttmn_press_threshold) plus DLMn -- NOT TTMn's level, so this is "
         "not comparable with ttmn_press_threshold. A level would stay saturated at 50 for as "
         "long as DNp02 is latched."),
        ("ttmn_gain", "float", 0.0, 10.0, 0.1,
         "Drive added per unit of TTMn rise, where TTMn is measured as a multiple of "
         "jump.ttmn_press_threshold (3.0): a 0 -> 50 rise is about 16.7 units."),
        ("dlmn_gain", "float", 0.0, 1.0, 0.01,
         "Drive added per frame per unit of DLMn activity (0 to ~8 on a pit). Sustained DLMn "
         "lengthens the hold: a graded long jump instead of a binary choice."),
        ("release_on_landing", "bool", 0, 1, 1,
         "Release A for one frame when Mario lands (RAM 0x001D returns to 0) and clear the drive, "
         "so the next jump is a fresh press -- the NES ignores a held A. Compared against the "
         "previous frame's player state.")],
    "dnp02_refractory": [("refractory_steps", "int", 1, 50, 1, _REFRACTORY_TIP.format(
        extra="Also compared against dnp02.spike_threshold / alpha (0.33), the drive that re-fires DNp02."))],
    "dnp01_refractory": [("refractory_steps", "int", 1, 50, 1, _REFRACTORY_TIP.format(
        extra="For DNp01 it sets the minimum spacing between Giant Fiber spikes."))],
    "mbon_readout": [(f"{p}_frac", "float", 0.0, 0.1, 0.001,
                      f"Bias current onto {label} per unit of the connectome-weighted MBON activity "
                      "(negative sign, like the existing MBON->DNa02 path). Compared against "
                      "mushroom_body.mbon_dna02_frac_l/r (0.0038 / 0.0063) -- same order of size.")
                     for p, label in (("dnp01", "DNp01 (jump)"), ("dlmn", "DLMn (long jump)"),
                                      ("dnp09", "DNp09 (speed)"), ("mdn", "MDN (backing up)"))],
}

CARD_ICON_PX = 160  # large, readable brain-map images -- ease-of-use redesign


class CircuitsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        shuffle_box = QGroupBox("Shuffled connectome (CLAUDE.md invariant 6)")
        shuffle_form = QFormLayout(shuffle_box)
        settings = window.get_tool_settings()
        current_seed = settings.circuits.shuffle_seed
        self.shuffle_checkbox = QCheckBox("Shuffle edges (same neurons, same degree, random wiring)")
        self.shuffle_checkbox.setChecked(current_seed is not None)
        self.shuffle_checkbox.toggled.connect(self._on_shuffle_toggled)
        shuffle_form.addRow(self.shuffle_checkbox)
        self.shuffle_seed_spin = NoScrollSpinBox()
        self.shuffle_seed_spin.setRange(0, 2_000_000_000)
        self.shuffle_seed_spin.setValue(current_seed or 0)
        self.shuffle_seed_spin.setEnabled(current_seed is not None)
        self.shuffle_seed_spin.valueChanged.connect(self._on_shuffle_seed_changed)
        shuffle_form.addRow("Shuffle seed", self.shuffle_seed_spin)
        layout.addWidget(shuffle_box)

        modules_box = QGroupBox("Controller modules (docs/CONTROL_AUDIT.md)")
        modules_layout = QVBoxLayout(modules_box)
        self.module_checkboxes: dict[str, QCheckBox] = {}
        for field_name, params_cls, label, tip in MODULE_TOGGLES:
            box = QCheckBox(label)
            box.setToolTip(tip)
            box.setChecked(getattr(window.get_config().modules, field_name) is not None)
            box.toggled.connect(lambda checked, f=field_name, c=params_cls: self._on_module_toggled(f, c, checked))
            modules_layout.addWidget(box)
            self.module_checkboxes[field_name] = box
            modules_layout.addWidget(self._build_module_editors(field_name))
        layout.addWidget(modules_box)

        # tool/SPEC_ui_retro.md section 3, "one home per setting": ONE
        # ParamForm, covering every group -- so _widget_by_path still has
        # every scalar (noise.sigma among them) no matter which card is
        # selected. The card grid only toggles which group boxes are
        # VISIBLE (ParamForm.show_only_groups), it never builds a second
        # form -- there is still exactly one writable widget per scalar.
        self.param_form = ParamForm(window.get_config())
        self.param_form.changed.connect(self._on_config_changed)
        # The form holds its own config snapshot; without this a later scalar
        # edit would re-emit it and silently undo a module toggle made elsewhere.
        window.config_changed.connect(self._sync_param_form)
        window.config_changed.connect(self._sync_module_editors)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        card_scroll = QScrollArea()
        card_scroll.setWidgetResizable(True)
        # A FlowLayout's own sizeHint() collapses to one card's width (it
        # has no notion of "how many columns would look good"), which a
        # QSplitter reads literally and shrinks this pane to fit -- an
        # explicit minimum width is what actually gets the splitter to
        # give the grid room to wrap past a single column.
        card_scroll.setMinimumWidth(2 * (CARD_ICON_PX + 40))
        card_area = QWidget()
        card_flow = FlowLayout(card_area, spacing=10)
        self._circuit_buttons: dict[str, QToolButton] = {}
        self._entries_by_id = {e.circuit_id: e for e in (*CIRCUIT_REGISTRY, OTHER_ENTRY)}
        for entry in self._entries_by_id.values():
            button = make_card_button(entry.display_name, circuit_card_pixmap(entry),
                                       CARD_ICON_PX, entry.description)
            button.clicked.connect(lambda _checked, cid=entry.circuit_id: self._select_circuit(cid))
            card_flow.addWidget(button)
            self._circuit_buttons[entry.circuit_id] = button
        card_scroll.setWidget(card_area)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        right_layout.addWidget(self._description_label)
        right_layout.addWidget(self.param_form, 1)

        splitter.addWidget(card_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        # QSplitter's stretch factor only governs EXTRA space on resize,
        # not the initial split -- without this, the card side started
        # too narrow for FlowLayout to ever wrap to more than one column.
        splitter.setSizes([700, 400])
        layout.addWidget(splitter, 1)

        self._select_circuit(CIRCUIT_REGISTRY[0].circuit_id)

    def _select_circuit(self, circuit_id: str) -> None:
        for cid, button in self._circuit_buttons.items():
            button.setChecked(cid == circuit_id)
        entry = self._entries_by_id[circuit_id]
        # Two lines (ease-of-use redesign): the circuit's own one-line
        # description, then where its populations/spec live.
        if entry.spec_path:
            second_line = f"See {entry.spec_path}."
        elif entry.populations:
            second_line = f"Populations: {', '.join(entry.populations)}."
        else:
            second_line = "No populations tracked in the live-brain map."
        self._description_label.setText(f"{entry.description}\n{second_line}")
        self.param_form.show_only_groups(set(entry.groups))

    def _build_module_editors(self, field_name: str) -> QWidget:
        """Editable parameters of one module, shown while it is on."""
        from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox
        from tool.ui.widgets.no_scroll_inputs import NoScrollDoubleSpinBox
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(24, 0, 0, 4)
        self.module_editors = getattr(self, "module_editors", {})
        self.module_editor_boxes = getattr(self, "module_editor_boxes", {})
        params = getattr(self._window.get_config().modules, field_name)
        shown = params if params is not None else next(c for f, c, *_ in MODULE_TOGGLES if f == field_name)()
        specs = MODULE_PARAM_UI.get(field_name, [])
        if not specs:
            note = QLabel("No parameters: switching it on is the whole setting.")
            form.addRow(note)
        for name, kind, lo, hi, step, tip in specs:
            if kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(getattr(shown, name)))
                w.toggled.connect(lambda v, f=field_name, n=name: self._set_module_param(f, n, bool(v)))
            elif kind == "int":
                w = NoScrollSpinBox()
                w.setRange(int(lo), int(hi))
                w.setValue(int(getattr(shown, name)))
                w.valueChanged.connect(lambda v, f=field_name, n=name: self._set_module_param(f, n, int(v)))
            else:
                w = NoScrollDoubleSpinBox()
                w.setDecimals(4)
                w.setRange(float(lo), float(hi))
                w.setSingleStep(float(step))
                w.setValue(float(getattr(shown, name)))
                w.valueChanged.connect(lambda v, f=field_name, n=name: self._set_module_param(f, n, float(v)))
            w.setToolTip(tip)
            label = QLabel(f"{name}  [{lo}\u2013{hi}]" if kind != "bool" else name)
            label.setToolTip(tip)
            form.addRow(label, w)
            self.module_editors[(field_name, name)] = w
        container.setVisible(params is not None)
        self.module_editor_boxes[field_name] = container
        return container

    def _set_module_param(self, field_name: str, name: str, value) -> None:
        config = self._window.get_config()
        params = getattr(config.modules, field_name)
        if params is None or getattr(params, name) == value:
            return
        modules = dataclasses.replace(config.modules, **{field_name: dataclasses.replace(params, **{name: value})})
        self._window.set_config(dataclasses.replace(config, modules=modules))

    def _sync_module_editors(self, config) -> None:
        """Module parameter widgets follow the config (a slider or preset can
        switch a module on or change a value from elsewhere)."""
        for (field_name, name), w in getattr(self, "module_editors", {}).items():
            params = getattr(config.modules, field_name)
            box = self.module_editor_boxes.get(field_name)
            if box is not None:
                box.setVisible(params is not None)
            cb = self.module_checkboxes.get(field_name)
            if cb is not None and cb.isChecked() != (params is not None):
                cb.blockSignals(True)
                cb.setChecked(params is not None)
                cb.blockSignals(False)
            if params is None:
                continue
            value = getattr(params, name)
            w.blockSignals(True)
            w.setChecked(bool(value)) if isinstance(w, QCheckBox) else w.setValue(value)
            w.blockSignals(False)

    def _sync_param_form(self, config) -> None:
        if config is not self.param_form._config:
            self.param_form.set_config(config)

    def _on_module_toggled(self, field_name: str, params_cls, checked: bool) -> None:
        config = self._window.get_config()
        modules = dataclasses.replace(config.modules, **{field_name: params_cls() if checked else None})
        self._window.set_config(dataclasses.replace(config, modules=modules))
        box = self.module_editor_boxes.get(field_name)
        if box is not None:
            box.setVisible(checked)
            params = getattr(modules, field_name)
            for (f, name), w in self.module_editors.items():   # show the fresh defaults
                if f == field_name and params is not None:
                    w.blockSignals(True)
                    value = getattr(params, name)
                    w.setChecked(bool(value)) if isinstance(w, QCheckBox) else w.setValue(value)
                    w.blockSignals(False)

    def _on_shuffle_toggled(self, checked: bool) -> None:
        self.shuffle_seed_spin.setEnabled(checked)
        seed = self.shuffle_seed_spin.value() if checked else None
        settings = self._window.get_tool_settings()
        circuits = dataclasses.replace(settings.circuits, shuffle_seed=seed)
        self._window.set_tool_settings(dataclasses.replace(settings, circuits=circuits))

    def _on_shuffle_seed_changed(self, value: int) -> None:
        if not self.shuffle_checkbox.isChecked():
            return
        settings = self._window.get_tool_settings()
        circuits = dataclasses.replace(settings.circuits, shuffle_seed=value)
        self._window.set_tool_settings(dataclasses.replace(settings, circuits=circuits))

    def _on_config_changed(self, config) -> None:
        self._window.set_config(config)

    def _preset_data(self) -> dict:
        return {
            "config": self._window.get_config().to_dict(),
            "shuffle_seed": self._window.get_tool_settings().circuits.shuffle_seed,
        }

    def _apply_preset(self, data: dict) -> None:
        self._window.set_config(config_from_dict(data["config"]))
        settings = self._window.get_tool_settings()
        circuits = dataclasses.replace(settings.circuits, shuffle_seed=data["shuffle_seed"])
        self._window.set_tool_settings(dataclasses.replace(settings, circuits=circuits))
        self._window.reload_tab("circuits")
