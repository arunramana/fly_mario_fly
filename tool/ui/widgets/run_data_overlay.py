"""tool/ui/widgets/run_data_overlay.py -- the Data panel's content: the
run summary on top, then every telemetry column for the current frame,
grouped. Scrollable read-only text.

The telemetry has no jump_cooldown/jump_hold column (they are FullPolicy
state, never written to the CSV), so the cooldown/hold group shows the
habituation levels and which pathway committed -- the recorded part of
that state -- rather than inventing values.
"""

from __future__ import annotations

import html

from PySide6.QtWidgets import QTextEdit

GROUPS = [
    ("Position / motion", ["frame", "mario_x", "mario_size", "direction", "mdn", "mdn_backing_up"]),
    ("Buttons", ["press_a", "press_b", "long_jump", "climb", "conflict"]),
    ("Looming", ["theta", "dtheta", "d_px", "frames_to_contact", "lc4", "lplc2",
                 "lc4_l", "lc4_r", "lplc2_l", "lplc2_r"]),
    ("Odour", ["hungry", "odor_l", "odor_r", "raw_odor_l", "raw_odor_r", "orn_a_l", "orn_a_r",
               "avers_l", "avers_r", "avoid_odor"]),
    ("Gap / terrain", ["gap", "refusing", "qblock_hit"]),
    ("Neurons", ["mem", "spike", "ttmn", "ttmn_dnp02", "spike_dnp02", "dna01", "dna02",
                 "dna01_l", "dna01_r", "dna02_l", "dna02_r", "dnp09", "dlmn", "r_team", "l_team",
                 "is_r_mask_sum", "is_l_mask_sum"]),
    ("Motor / MBON readout", ["motor_drive", "mbon_agg", "mbon_dnp01", "mbon_dlmn",
                              "mbon_dnp09", "mbon_mdn"]),
    ("Arousal (pC1)", ["arousal", "pc1_h", "pc1_drive_steer_r", "pc1_drive_steer_l",
                       "pc1_drive_dnp09", "pc1_drive_gf"]),
    ("Cooldown / hold (recorded part)", ["pathway_fired", "hab_escape", "hab_climb"]),
]
SUMMARY_SKIP = {"mb_weights"}


def _fmt(value) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if value != value:
            return "--"
        return f"{value:.3g}" if abs(value) < 1e-3 and value != 0 else f"{value:.3f}"
    return str(value)


class DataOverlayContent(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dataOverlayContent")
        self.setReadOnly(True)
        self._summary: dict | None = None
        self._row: dict | None = None
        self._render()

    def set_summary(self, summary: dict | None) -> None:
        self._summary = summary
        self._render()

    def update_from_row(self, row: dict | None) -> None:
        self._row = dict(row) if row else None
        self._render()

    def _render(self) -> None:
        parts = ["<b>RUN SUMMARY</b>"]
        if self._summary:
            parts += [f"{html.escape(k)} = {html.escape(_fmt(v))}"
                      for k, v in sorted(self._summary.items()) if k not in SUMMARY_SKIP]
        else:
            parts.append("(no run selected)")
        parts.append("<br><b>CURRENT FRAME</b>")
        if not self._row:
            parts.append("(no frame)")
        else:
            used = set()
            for title, cols in GROUPS:
                present = [c for c in cols if c in self._row]
                if not present:
                    continue
                parts.append(f"<br><b>{title}</b>")
                parts += [f"{c} = {html.escape(_fmt(self._row[c]))}" for c in present]
                used.update(present)
            rest = [c for c in self._row if c not in used]
            if rest:
                parts.append("<br><b>Other</b>")
                parts += [f"{c} = {html.escape(_fmt(self._row[c]))}" for c in rest]
        scroll = self.verticalScrollBar().value()
        self.setHtml("<br>".join(parts))
        self.verticalScrollBar().setValue(scroll)
