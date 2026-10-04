"""tool/ui/tabs/results.py -- tab 10: E1 results, real vs shuffled connectome (docs/SPEC_tool_phase2.md section 7).
Shows a saved evaluation (projects/<name>/brain_eval.json) with Wilson 95% intervals and the plan's pass criterion, and
runs a new one (20 held-out seeds, 3000-3019) in a child process. The same numbers are printed by `python -m brain.e1`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from tool.core.brain_runner import load_brain_evals
from tool.ui.widgets.scroll_page import install_scroll_page

SUMMARY_COLUMNS = ("Arm", "Survived", "95% CI", "Deaths", "GF before contact", "A-press runs", "theta at GF (median, deg)",
                   "distance at GF (median, px)", "GF crossed threshold", "GF output / TTMn max (Hz)")
ARM_LABELS = {"lesion_gf": "lesion_gf (control)"}      # the GF-lesion arm is a control only: labelled as such
EPISODE_COLUMNS = ("Arm", "Seed", "Outcome", "Survived", "GF before contact", "theta at GF (deg)", "distance at GF (px)", "A frames")


def _pct(x) -> str:
    return f"{100 * x:.0f}%"


def summary_rows(result: dict) -> list[list[str]]:
    rows = []
    for arm in result.get("arms", ["real", "shuffled"]):
        s = result[arm]
        th, dd = s["theta_at_gf_deg"], s["distance_at_gf_px"]
        rows.append([ARM_LABELS.get(arm, arm), f"{s['survived']}/{s['n']}", f"{_pct(s['survived_ci'][0])}-{_pct(s['survived_ci'][1])}",
                     str(s["deaths"]), f"{s['gf_before_contact']}/{s['n']}", f"{s['a_pressed_runs']}/{s['n']}",
                     "-" if th["median"] is None else f"{th['median']:.1f}", "-" if dd["median"] is None else f"{dd['median']:.0f}",
                     f"{s['gf_fired']}/{s['n']}", f"{s.get('gf_output_max_hz', 0.0):.2f} / {s.get('ttmn_max_hz', 0.0):.3f}"])
    return rows


def criterion_text(result: dict) -> str:
    c, real, shuf = result["criterion"], result["real"], result["shuffled"]
    met = real["survived"] >= c["real_survived_min"] and shuf["survived"] <= c["shuffled_survived_max"]
    return (f"Plan criterion (reported, not tuned): real >= {c['real_survived_min']}/{c['n']} and shuffled <= "
            f"{c['shuffled_survived_max']}/{c['n']} -> {'met' if met else 'not met'}")


class ResultsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._evals: list[dict] = []
        content = QWidget()
        layout = QVBoxLayout(content)
        install_scroll_page(self, content)
        top = QHBoxLayout()
        self.history_combo = QComboBox()
        self.history_combo.currentIndexChanged.connect(self._show_selected)
        self.run_button = QPushButton("Run E1 evaluation (seeds 3000-3019, held-out, run once)")
        self.run_button.clicked.connect(self._start_eval)
        top.addWidget(QLabel("Saved evaluation:"))
        top.addWidget(self.history_combo, 1)
        top.addWidget(self.run_button)
        layout.addLayout(top)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.header_label = QLabel("No E1 evaluation saved for this project yet.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)
        self.summary_table = self._table(SUMMARY_COLUMNS, 3)
        layout.addWidget(self.summary_table)
        self.criterion_label = QLabel("")
        self.criterion_label.setWordWrap(True)
        layout.addWidget(self.criterion_label)
        layout.addWidget(QLabel("Per episode:"))
        self.episode_table = self._table(EPISODE_COLUMNS, 0)
        layout.addWidget(self.episode_table, 1)
        window.brain_runs.eval_finished.connect(self._on_eval_finished)
        window.brain_runs.eval_status.connect(self.status_label.setText)
        self.refresh()

    @staticmethod
    def _table(columns, rows) -> QTableWidget:
        t = QTableWidget(rows, len(columns))
        t.setHorizontalHeaderLabels(list(columns))
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def refresh(self) -> None:
        evals = load_brain_evals(self._window.project.name)
        self._evals = evals
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        for e in evals:
            self.history_combo.addItem(f"{e.get('time', '?')[:19]}  seeds {e['seeds'][0]}-{e['seeds'][1]}")
        self.history_combo.blockSignals(False)
        if evals:
            self.history_combo.setCurrentIndex(len(evals) - 1)
            self._show(evals[-1])

    def _show_selected(self, index: int) -> None:
        if 0 <= index < len(self._evals):
            self._show(self._evals[index])

    def _show(self, result: dict) -> None:
        st = result["stamp"]
        self.header_label.setText(
            f"E1, scene {result['scene']['id']} ({result['scene']['scene_hash']}), seeds {result['seeds'][0]}-{result['seeds'][1]}, "
            f"survived = alive {result['grace_frames']} frames after the Goomba stops being a threat. Network {st['build_hash']} "
            f"({st['neurons']} neurons), calibration {st['calibration_hash']}.")
        rows = summary_rows(result)
        self.summary_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                self.summary_table.setItem(r, c, QTableWidgetItem(text))
        self.criterion_label.setText(criterion_text(result))
        eps = result["episodes"]
        self.episode_table.setRowCount(len(eps))
        for r, e in enumerate(eps):
            vals = [ARM_LABELS.get(e["arm"], e["arm"]), str(e["seed"]), e["outcome"], "yes" if e["survived"] else "no", "yes" if e["gf_before_contact"] else "no",
                    "-" if e["theta_at_gf_deg"] is None else f"{e['theta_at_gf_deg']:.1f}",
                    "-" if e["distance_at_gf_px"] is None else f"{e['distance_at_gf_px']:.0f}", str(e["a_frames"])]
            for c, text in enumerate(vals):
                self.episode_table.setItem(r, c, QTableWidgetItem(text))

    def _start_eval(self) -> None:
        if self._window.brain_runs.start_eval():
            self.run_button.setEnabled(False)

    def _on_eval_finished(self, result) -> None:
        self.run_button.setEnabled(True)
        if result is not None:
            self.refresh()
