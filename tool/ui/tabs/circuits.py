"""tool/ui/tabs/circuits.py -- tab 4: a large grid of circuit cards (real brain-map
images, render.brain_panel.highlight_populations) at the top-left; clicking a card
opens an inspector on its right with that circuit's own config/params.py group(s)
(the single, eagerly-built ParamForm), its related controller modules and its
control rules, as collapsible lists with "k/n on" badges. The whole tab is ONE page
scroll (no nested scroll areas), and every spin box/slider ignores the wheel unless
focused, so the wheel always scrolls the page. The shuffled-connectome switch (C5)
sits in a slim bar above the grid. Presets for this tab live in the header's
Presets menu (main_window.py), not a per-tab bar.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSlider, QToolButton, QVBoxLayout, QWidget,
)

from config.params import CONTROL_RULE_LABELS, ArousalParams, GapAheadParams, WallAheadParams, MbonReadoutParams, Dnp01RefractoryParams, Dnp02RefractoryParams, MbSpatialInputParams, MotorDirectParams, PagePerceptionParams, QBlockAheadParams, MbGapSpeedInputParams
from config.project_config import from_dict as config_from_dict
from tool.core.circuit_manifest import CIRCUIT_REGISTRY, OTHER_ENTRY
from tool.ui.widgets.card_button import make_card_button
from tool.ui.widgets.circuit_card_image import circuit_card_pixmap
from tool.ui.widgets.collapsible_section import CollapsibleSection
from tool.ui.widgets.no_scroll_inputs import NoScrollSlider, NoScrollSpinBox
from tool.ui.widgets.param_form import FIELD_MAX_WIDTH, ParamForm
from tool.ui.widgets.reflow_grid import ReflowGrid

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
    ("wall_ahead", WallAheadParams, "Wall / step ahead (perception)",
     "Pipes, stairs and block stacks from the tile RAM, as distance and height, fed to the circuit as "
     "looming (LC4/LPLC2) and/or a takeoff current onto DNp01. A stimulus only: the fly decides."),
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
    ("mb_gap_speed_inputs", MbGapSpeedInputParams, "MB gap width + own speed (perception)",
     "Two more Kenyon-cell inputs: the width of the next pit and Mario's own horizontal speed (RAM 0x0057). "
     "Stimulus only. docs/SPEC_learning_v3.md A2."),
    ("qblock_ahead", QBlockAheadParams, "? block ahead (perception)",
     "Unhit ? blocks at or ahead of Mario as distance and height, fed to the mushroom body as two extra "
     "Kenyon-cell inputs and, if looming_gain > 0, as a weak looming cue. A stimulus only: the fly "
     "decides. Scaled by the Question Block's Cue weight in the Objects tab. docs/SPEC_learning_v2.md"),
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
    "page_perception": [("ignore_behind", "bool", 0, 1, 1,
        "An enemy behind Mario produces no looming (it is outside the frontal visual field). Off: theta from |d| "
        "for enemies on both sides, so a receding enemy keeps driving the left hemisphere -- the source of the "
        "TTMn plateau (docs/SPEC_learning_v3.md A4).")],
    "mb_gap_speed_inputs": [("perceive_tiles", "int", 1, 16, 1,
        "How many tiles ahead the pit width is read. Compared against the takeoff lookahead (gap_lookahead_tiles).")],
    "gap_ahead": [("perceive_tiles", "int", 1, 16, 1,
                   "How many tiles ahead the pit-edge input starts. Compared against the distance "
                   "to the nearest non-ground tile (tiles): inside this range the gap input is "
                   "width x (n - d + 1) / n, reaching today's full strength at the edge. The "
                   "current itself is still takeoff.gap_gain x that value.")],
    "wall_ahead": [
        ("perceive_tiles", "int", 1, 16, 1,
         "How many tiles ahead the wall is perceived. Compared against the distance to the first "
         "ground-attached solid column (tiles); also sets the takeoff ramp: full strength at 1 tile."),
        ("looming_gain", "float", 0.0, 10.0, 0.1,
         "Scale on the wall's looming angle theta = 2*arctan(height_px / (2*distance_px)) into the "
         "right-hemisphere LC4/LPLC2 drive, the same channel an enemy uses (a Goomba is 16 px wide, a "
         "2-tile pipe 32 px). 0 = looming route off."),
        ("takeoff_gain", "float", 0.0, 10.0, 0.1,
         "Current onto DNp01 per tile of wall height, ramping up as the wall nears. Compared against "
         "takeoff.gap_gain (1.0 per tile of pit width). 0 = takeoff route off.")],
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
        ("adapt_frames", "float", 0.0, 600.0, 5.0,
         "Muscle adaptation: a TTMn rise counts only above a slow baseline with this time constant (frames), so a "
         "sustained 4->8->17 cycle stops holding A while a fresh onset still drives fully. 0 = off."),
        ("buttons", "bool", 0, 1, 1,
         "Turn on the Down / Up / Left muscles below (each a leaky integral of its neurons, pressed above its threshold). "
         "Down = DNp03/DNp06/DNp11, Up = DNg40/DNp05 (looming-driven, roles are a hypothesis), Left = DNa01/02 left minus right."),
        ("button_decay", "float", 0.0, 0.999, 0.01, "Per-frame decay of the three button drives (tau = 1/(1-decay) frames)."),
        ("down_gain", "float", 0.0, 20.0, 0.1, "Drive added per unit of Down-DN activity (median 0.19, peak 1.5 on learn_1)."),
        ("down_threshold", "float", 0.0, 100.0, 0.1, "Down is held while its drive is at or above this."),
        ("up_gain", "float", 0.0, 20.0, 0.1, "Drive added per unit of Up-DN activity (peak 0.76 on learn_1)."),
        ("up_threshold", "float", 0.0, 100.0, 0.1, "Up is held while its drive is at or above this."),
        ("left_gain", "float", 0.0, 20.0, 0.1, "Drive added per unit of DNa01/02 left-minus-right team activity."),
        ("left_threshold", "float", 0.0, 100.0, 0.1, "Left replaces Right while its drive is at or above this."),
        ("posture_g", "float", 0.1, 1.2, 0.05, "Gain of the posture circuit (spectral radius 0.9993 at g=1: keep below ~1)."),
        ("release_on_landing", "bool", 0, 1, 1,
         "Release A for one frame when Mario lands (RAM 0x001D returns to 0) and clear the drive, "
         "so the next jump is a fresh press -- the NES ignores a held A. Compared against the "
         "previous frame's player state.")],
    "dnp02_refractory": [("refractory_steps", "int", 1, 50, 1, _REFRACTORY_TIP.format(
        extra="Also compared against dnp02.spike_threshold / alpha (0.33), the drive that re-fires DNp02."))],
    "dnp01_refractory": [("refractory_steps", "int", 1, 50, 1, _REFRACTORY_TIP.format(
        extra="For DNp01 it sets the minimum spacing between Giant Fiber spikes."))],
    "qblock_ahead": [
        ("perceive_tiles", "int", 1, 16, 1,
         "How many tiles ahead an unhit ? block is perceived. Compared against the block's distance in tiles "
         "(0 = overhead): closeness = (n - d) / n, so 1 overhead and 0 at the edge of the range."),
        ("looming_gain", "float", 0.0, 10.0, 0.1,
         "Scale on the block's looming angle theta = 2*arctan(16 px / (2*distance_px)) into the right-hemisphere "
         "LC4/LPLC2 drive. Compared against wall_ahead.looming_gain (1.0). 0 = the looming route is off; the "
         "two Kenyon-cell inputs are always on while the module is.")],
    "mbon_readout": [(f"{p}_frac", "float", 0.0, 1.0, 0.005,
                      f"Bias current onto {label} per unit of the connectome-weighted MBON activity "
                      "(negative sign, like the existing MBON->DNa02 path). Compared against "
                      "mushroom_body.mbon_dna02_frac_l/r (0.0038 / 0.0063) -- same order of size. Range 0-1; "
                      "see docs/RUNS.md for the value at which the readout starts to change behaviour.")
                     for p, label in (("dnp01", "DNp01 (jump)"), ("dlmn", "DLMn (long jump)"),
                                      ("dnp09", "DNp09 (speed)"), ("mdn", "MDN (backing up)"))],
}

CARD_ICON_PX = 200   # brain maps first: big, readable card images (the ceiling; see card_icon_px)
CARD_ICON_MIN_PX = 96
CARD_ICON_SCREEN_FRACTION = 0.11   # icon edge as a share of the screen's available width
INSPECTOR_MIN_EM = 24             # inspector min width, in line heights of the current font


def card_icon_px(available_width: int) -> int:
    """Card image edge from the screen, not a constant: 200px on a big monitor, shrinking to 96px
    on a small laptop so the card column and the inspector both still fit."""
    return max(CARD_ICON_MIN_PX, min(CARD_ICON_PX, int(available_width * CARD_ICON_SCREEN_FRACTION)))
SLIDER_STEPS = 1000
SWITCH_QSS = ("QCheckBox#switch::indicator { width: 30px; height: 16px; border-radius: 8px; "
              "background: #9aa0a6; border: 1px solid #777; } "
              "QCheckBox#switch::indicator:checked { background: #2a9d8f; }")


class CircuitsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # One scroll area for the whole tab: cards, inspector, modules and rules all scroll
        # together with the wheel.
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        self.page_scroll.setWidget(content)
        outer.addWidget(self.page_scroll)

        layout.addLayout(self._build_shuffle_bar())

        body = QHBoxLayout()
        body.setSpacing(16)
        layout.addLayout(body)
        self._build_cards(body)
        body.addWidget(self._build_inspector(), 2)
        layout.addStretch(1)

        # The form holds its own config snapshot; without this a later scalar
        # edit would re-emit it and silently undo a module toggle made elsewhere.
        window.config_changed.connect(self._sync_param_form)
        window.config_changed.connect(self._sync_module_editors)
        window.config_changed.connect(self._sync_rules)
        self._select_circuit(CIRCUIT_REGISTRY[0].circuit_id)

    # ---- construction --------------------------------------------------------

    def _build_shuffle_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        current_seed = self._window.get_tool_settings().circuits.shuffle_seed
        self.shuffle_checkbox = QCheckBox("Shuffled connectome")
        self.shuffle_checkbox.setObjectName("switch")
        self.shuffle_checkbox.setStyleSheet(SWITCH_QSS)
        self.shuffle_checkbox.setToolTip("CLAUDE.md invariant 6: same neurons, same degree, random wiring.")
        self.shuffle_checkbox.setChecked(current_seed is not None)
        self.shuffle_checkbox.toggled.connect(self._on_shuffle_toggled)
        self.shuffle_seed_spin = NoScrollSpinBox()
        self.shuffle_seed_spin.setRange(0, 2_000_000_000)
        self.shuffle_seed_spin.setMaximumWidth(FIELD_MAX_WIDTH)
        self.shuffle_seed_spin.setPrefix("seed ")
        self.shuffle_seed_spin.setValue(current_seed or 0)
        self.shuffle_seed_spin.setEnabled(current_seed is not None)
        self.shuffle_seed_spin.valueChanged.connect(self._on_shuffle_seed_changed)
        bar.addWidget(self.shuffle_checkbox)
        bar.addWidget(self.shuffle_seed_spin)
        bar.addStretch(1)
        return bar

    def _build_cards(self, body: QHBoxLayout) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        icon_px = card_icon_px(screen.availableGeometry().width())
        # Reflows its column count to the width it is given (1..n cards across).
        card_area = ReflowGrid(cell_width=icon_px + 24, spacing=10)
        self._circuit_buttons: dict[str, QToolButton] = {}
        self._entries_by_id = {e.circuit_id: e for e in (*CIRCUIT_REGISTRY, OTHER_ENTRY)}
        for i, entry in enumerate(self._entries_by_id.values()):
            button = make_card_button(entry.display_name, circuit_card_pixmap(entry),
                                       icon_px, entry.description)
            button.clicked.connect(lambda _checked, cid=entry.circuit_id: self._select_circuit(cid))
            card_area.add(button)
            self._circuit_buttons[entry.circuit_id] = button
        self.card_area = card_area
        body.addWidget(card_area, 3)

    def _build_inspector(self) -> QWidget:
        window = self._window
        inspector = QWidget()
        inspector.setMinimumWidth(INSPECTOR_MIN_EM * self.fontMetrics().height())
        box = QVBoxLayout(inspector)
        box.setContentsMargins(0, 0, 0, 0)
        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        box.addWidget(self._description_label)

        # tool/SPEC_ui_retro.md section 3, "one home per setting": ONE ParamForm covering every
        # group, so _widget_by_path still has every scalar (noise.sigma among them) whichever
        # card is selected; the cards only toggle which group boxes are VISIBLE.
        self.param_form = ParamForm(window.get_config(), scrollable=False)
        self.param_form.changed.connect(self._on_config_changed)
        box.addWidget(self.param_form)

        self.modules_section = CollapsibleSection("Controller modules")
        self.module_checkboxes: dict[str, QCheckBox] = {}
        self.module_editors: dict = {}
        self.module_editor_boxes: dict[str, QWidget] = {}
        self._module_sliders: dict = {}
        self._module_rows: dict[str, QWidget] = {}
        for field_name, params_cls, label, tip in MODULE_TOGGLES:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox(label)
            cb.setToolTip(tip)
            cb.setChecked(getattr(window.get_config().modules, field_name) is not None)
            cb.toggled.connect(lambda checked, f=field_name, c=params_cls: self._on_module_toggled(f, c, checked))
            row_layout.addWidget(cb)
            row_layout.addWidget(self._build_module_editors(field_name))
            self.modules_section.add_widget(row)
            self.module_checkboxes[field_name] = cb
            self._module_rows[field_name] = row
        box.addWidget(self.modules_section)

        self.rules_section = CollapsibleSection("Control rules")
        self.rule_checkboxes: dict[str, QCheckBox] = {}
        for rule, label in CONTROL_RULE_LABELS.items():
            cb = QCheckBox(label)
            cb.setToolTip("Unchecked: the rule is removed and the circuit alone decides. "
                          "Defaults are all checked (behaviour unchanged).")
            cb.setChecked(getattr(window.get_config().rules, rule))
            cb.toggled.connect(lambda checked, r=rule: self._on_rule_toggled(r, checked))
            self.rules_section.add_widget(cb)
            self.rule_checkboxes[rule] = cb
        # The forced GradedPitModule (audit row 17) already has its one writable home in the
        # Goal tab; shown here read-only so every rule is visible in one place.
        self.graded_pit_mirror = QCheckBox("Graded pit response, forced jump/B (row 17) -- set in the Goal tab")
        self.graded_pit_mirror.setEnabled(False)
        self.graded_pit_mirror.setChecked(window.get_config().scenario.graded_pit_response)
        self.rules_section.add_widget(self.graded_pit_mirror)
        box.addWidget(self.rules_section)
        box.addStretch(1)
        return inspector

    def _select_circuit(self, circuit_id: str) -> None:
        for cid, button in self._circuit_buttons.items():
            button.setChecked(cid == circuit_id)
        entry = self._entries_by_id[circuit_id]
        if entry.spec_path:
            second_line = f"See {entry.spec_path}."
        elif entry.populations:
            second_line = f"Populations: {', '.join(entry.populations)}."
        else:
            second_line = "No populations tracked in the live-brain map."
        self._description_label.setText(f"{entry.display_name}: {entry.description}\n{second_line}")
        self.param_form.show_only_groups(set(entry.groups))
        self._selected = entry
        for field_name, row in self._module_rows.items():
            row.setVisible(field_name in entry.modules)
        for rule, cb in self.rule_checkboxes.items():
            cb.setVisible(rule in entry.rules)
        self.graded_pit_mirror.setVisible("graded_pit_response" in entry.rules)
        self.modules_section.setVisible(bool(entry.modules))
        self.rules_section.setVisible(bool(entry.rules))
        self._update_badges()

    def _update_badges(self) -> None:
        """"Control rules (k/n on)" / "Controller modules (k/n on)" for the selected circuit."""
        entry, config = self._selected, self._window.get_config()
        mods_on = sum(getattr(config.modules, f) is not None for f in entry.modules)
        rules_on = sum(getattr(config.rules, r) for r in entry.rules if r != "graded_pit_response")
        rules_on += int("graded_pit_response" in entry.rules and config.scenario.graded_pit_response)
        self.modules_section.set_title(f"Controller modules ({mods_on}/{len(entry.modules)} on)")
        self.rules_section.set_title(f"Control rules ({rules_on}/{len(entry.rules)} on)")

    def _build_module_editors(self, field_name: str) -> QWidget:
        """Editable parameters of one module, shown while it is on. Every ranged field gets a
        slider beside its (width-capped) spin box; the spin box stays the one writable path."""
        from tool.ui.widgets.no_scroll_inputs import NoScrollDoubleSpinBox
        container = QWidget()
        form = QFormLayout(container)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setContentsMargins(24, 0, 0, 4)
        params = getattr(self._window.get_config().modules, field_name)
        shown = params if params is not None else next(c for f, c, *_ in MODULE_TOGGLES if f == field_name)()
        specs = MODULE_PARAM_UI.get(field_name, [])
        if not specs:
            form.addRow(QLabel("No parameters: switching it on is the whole setting."))
        for name, kind, lo, hi, step, tip in specs:
            if kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(getattr(shown, name)))
                w.toggled.connect(lambda v, f=field_name, n=name: self._set_module_param(f, n, bool(v)))
                editor = w
            else:
                if kind == "int":
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
                w.setMaximumWidth(FIELD_MAX_WIDTH)
                slider = NoScrollSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, SLIDER_STEPS)
                slider.setToolTip(f"{lo} to {hi}")
                self._link_slider(w, slider, float(lo), float(hi))
                self._module_sliders[(field_name, name)] = slider
                editor = QWidget()
                row = QHBoxLayout(editor)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(w)
                row.addWidget(slider, 1)
            w.setToolTip(tip)
            label = QLabel(f"{name}  [{lo}–{hi}]" if kind != "bool" else name)
            label.setToolTip(tip)
            form.addRow(label, editor)
            self.module_editors[(field_name, name)] = w
        container.setVisible(params is not None)
        self.module_editor_boxes[field_name] = container
        return container

    @staticmethod
    def _link_slider(spin, slider: QSlider, lo: float, hi: float) -> None:
        """Slider <-> spin box over [lo, hi]; a value outside the range pins the slider at its end."""
        span = (hi - lo) or 1.0
        is_int = isinstance(spin, NoScrollSpinBox)

        def to_slider(value) -> None:
            slider.blockSignals(True)
            slider.setValue(int(round(SLIDER_STEPS * (min(hi, max(lo, value)) - lo) / span)))
            slider.blockSignals(False)

        def from_slider(raw: int) -> None:
            value = lo + span * raw / SLIDER_STEPS
            spin.setValue(round(value) if is_int else value)

        slider.valueChanged.connect(from_slider)
        spin.valueChanged.connect(to_slider)
        to_slider(spin.value())

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
            self._sync_slider_of(field_name, name, w)
        self._update_badges()

    def _sync_slider_of(self, field_name: str, name: str, spin) -> None:
        """The spin's own signal was blocked, so its slider must be moved by hand."""
        slider = self._module_sliders.get((field_name, name))
        if slider is not None:
            lo, hi = spin.minimum(), spin.maximum()
            slider.blockSignals(True)
            slider.setValue(int(round(SLIDER_STEPS * (min(hi, max(lo, spin.value())) - lo) / ((hi - lo) or 1.0))))
            slider.blockSignals(False)

    def _on_rule_toggled(self, rule: str, checked: bool) -> None:
        config = self._window.get_config()
        if getattr(config.rules, rule) == checked:
            return
        self._window.set_config(dataclasses.replace(config, rules=dataclasses.replace(config.rules, **{rule: checked})))

    def _sync_rules(self, config) -> None:
        """Rule checkboxes (and the read-only graded-pit mirror) follow the config."""
        for rule, box in self.rule_checkboxes.items():
            if box.isChecked() != getattr(config.rules, rule):
                box.blockSignals(True)
                box.setChecked(getattr(config.rules, rule))
                box.blockSignals(False)
        self.graded_pit_mirror.setChecked(config.scenario.graded_pit_response)
        self._update_badges()

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
            self._update_badges()
            params = getattr(modules, field_name)
            for (f, name), w in self.module_editors.items():   # show the fresh defaults
                if f == field_name and params is not None:
                    w.blockSignals(True)
                    value = getattr(params, name)
                    w.setChecked(bool(value)) if isinstance(w, QCheckBox) else w.setValue(value)
                    w.blockSignals(False)
                    self._sync_slider_of(f, name, w)

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
