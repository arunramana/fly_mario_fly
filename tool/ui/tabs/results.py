"""tool/ui/tabs/results.py -- tab 10: results of E0, E1 and E3, real vs shuffled connectome (docs/SPEC_tool_phase2.md section 7,
docs/SPEC_phase3.md section 6). Shows a saved evaluation (projects/<name>/brain_eval.json) with Wilson 95% intervals and the
plan's pass criterion, and runs a new one (20 held-out seeds: E1 3000, E0 4000, E3 5100) in a child process. The same numbers are
printed by `python -m brain.e1` and `python -m brain.goal_eval`. Every evaluation shows the GF-crossed count and the GF output
and TTMn maxima for every arm.
"""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from tool.core.brain_runner import load_brain_evals
from tool.ui.widgets.scroll_page import install_scroll_page

SUMMARY_COLUMNS = ("Arm", "Survived", "95% CI", "Deaths", "GF before contact", "A-press runs", "theta at GF (median, deg)",
                   "distance at GF (median, px)", "GF crossed threshold", "GF output / TTMn max (Hz)")
ARM_LABELS = {"real_no_obstacle": "real_no_obstacle (control)", "lesion_gf": "lesion_gf (control)", "shuffled_class": "shuffled_class (class-preserving, informative)",
              "real_no_landmark": "real_no_landmark (control)", "real_no_pursuit": "real_no_pursuit (control)"}
GOAL_SUMMARY_COLUMNS = ("Arm", "Reached", "95% CI", "Deaths", "Lost / timeouts", "Median frames to reach", "Mean Left frames",
                        "GF crossed threshold", "GF output / TTMn max (Hz)")
GOAL_EPISODE_COLUMNS = ("Arm", "Seed", "Outcome", "Reached", "Frames", "Max x", "GF crossed", "GF output max (Hz)", "TTMn max (Hz)",
                        "Left / Right / B frames")
BASELINE_SUMMARY_COLUMNS = ("Arm", "Max x mean (bootstrap 95% CI)", "Max x median", "How runs ended", "Goombas jumped / encountered",
                            "A-tap episodes", "Power-up collected", "GF crossed threshold", "GF output / TTMn max (Hz)")
BASELINE_EPISODE_COLUMNS = ("Arm", "Seed", "End", "Frames", "Max x", "Goombas jumped / encountered", "First A run", "Power-up",
                            "GF output max (Hz)", "TTMn max (Hz)")
E2A_SUMMARY_COLUMNS = ("Arm", "Cleared", "95% CI", "How runs ended", "GF before the face", "A-press runs (taps)",
                       "First A x / take-off x (median)", "GF output / TTMn max (Hz)")
E2A_EPISODE_COLUMNS = ("Arm", "Seed", "Outcome", "Cleared", "Frames", "Max x", "GF before face", "First A x / run", "Take-off x")
EVAL_EXPERIMENTS = ("E1", "E0", "E3", "E2a", "B11")
EVAL_SEEDS = {"E1": (3000, 3019), "E0": (4000, 4019), "E3": (5100, 5119), "E2a": (7100, 7119), "B11": (6100, 6119)}
EPISODE_COLUMNS = ("Arm", "Seed", "Outcome", "Survived", "GF before contact", "theta at GF (deg)", "distance at GF (px)", "A frames")


def _pct(x) -> str:
    return f"{100 * x:.0f}%"


def is_goal(result: dict) -> bool:
    return result.get("experiment", "E1") in ("E0", "E3")


def is_baseline(result: dict) -> bool:
    return result.get("experiment", "E1") == "B11"


def is_e2a(result: dict) -> bool:
    return result.get("experiment", "E1") == "E2a"


def summary_rows(result: dict) -> list[list[str]]:
    rows = []
    if is_e2a(result):
        for arm in result["arms"]:
            s = result[arm]
            lo, hi = s["cleared_ci"]
            taps = "none" if s["tap_fraction"] is None else f"{s['a_pressed_runs']} ({s['tap_episodes']} taps)"
            ends = ", ".join(f"{k} {v}" for k, v in s["end_reasons"].items() if v)
            rows.append([ARM_LABELS.get(arm, arm), f"{s['cleared']}/{s['n']}", f"{_pct(lo)}-{_pct(hi)}", ends,
                         f"{s['gf_before_face']}/{s['n']}", taps, f"{s['first_a_x_median']} / {s['takeoff_x_median']}",
                         f"{s.get('gf_output_max_hz', 0.0):.2f} / {s.get('ttmn_max_hz', 0.0):.3f}"])
        return rows
    if is_baseline(result):
        for arm in result["arms"]:
            s = result[arm]
            tap = "no A presses" if s["tap_fraction"] is None else f"{s['tap_episodes']}/{s['a_episodes']}"
            ends = ", ".join(f"{k} {v}" for k, v in s["end_reasons"].items() if v)
            rows.append([ARM_LABELS.get(arm, arm), f"{s['max_x_mean']:.0f} ({s['max_x_mean_ci'][0]:.0f}-{s['max_x_mean_ci'][1]:.0f})",
                         f"{s['max_x_median']:.0f}", ends, f"{s['goombas_jumped']} / {s['goombas_encountered']}", tap,
                         f"{s['collected']}/{s['n']}", f"{s['gf_fired']}/{s['n']}",
                         f"{s.get('gf_output_max_hz', 0.0):.2f} / {s.get('ttmn_max_hz', 0.0):.3f}"])
        return rows
    if is_goal(result):
        for arm in result["arms"]:
            s = result[arm]
            fr = s["frames_to_reach"]["median"]
            rows.append([ARM_LABELS.get(arm, arm), f"{s['reached']}/{s['n']}", f"{_pct(s['reached_ci'][0])}-{_pct(s['reached_ci'][1])}",
                         str(s["deaths"]), f"{s['lost']} / {s['timeouts']}", "-" if fr is None else f"{fr:.0f}",
                         f"{s['left_frames_mean']:.0f}", f"{s['gf_fired']}/{s['n']}",
                         f"{s.get('gf_output_max_hz', 0.0):.2f} / {s.get('ttmn_max_hz', 0.0):.3f}"])
        return rows
    for arm in result.get("arms", ["real", "shuffled"]):
        s = result[arm]
        th, dd = s["theta_at_gf_deg"], s["distance_at_gf_px"]
        rows.append([ARM_LABELS.get(arm, arm), f"{s['survived']}/{s['n']}", f"{_pct(s['survived_ci'][0])}-{_pct(s['survived_ci'][1])}",
                     str(s["deaths"]), f"{s['gf_before_contact']}/{s['n']}", f"{s['a_pressed_runs']}/{s['n']}",
                     "-" if th["median"] is None else f"{th['median']:.1f}", "-" if dd["median"] is None else f"{dd['median']:.0f}",
                     f"{s['gf_fired']}/{s['n']}", f"{s.get('gf_output_max_hz', 0.0):.2f} / {s.get('ttmn_max_hz', 0.0):.3f}"])
    return rows


def criterion_text(result: dict) -> str:
    if is_e2a(result):
        c = result["criterion"]
        real, shuf = result["real"], result.get("shuffled")
        met = real["cleared"] >= c["real_cleared_min"] and (shuf is None or shuf["cleared"] <= c["shuffled_cleared_max"])
        return (f"Criterion (stated in docs/SPEC_e2a.md before running): real >= {c['real_cleared_min']}/{c['n']} and degree shuffle <= "
                f"{c['shuffled_cleared_max']}/{c['n']} -> {'met' if met else 'not met'}. Class shuffle is informative only; real_no_obstacle "
                "(obstacle cue off) is expected to fail. The obstacle cue is a Mario's-eye-view assumption (no source for obstacle-triggered "
                "jumps in flies); the home landmark is an invented world cue.")
    if is_baseline(result):
        return ("Baseline, not a criterion: no pass/fail. Looming, pursuit, home landmark and (from 2026-10-05) obstacle expansion on; the home landmark is an invented world cue and obstacle expansion a Mario's-eye-view assumption. "
                f"Tap = first A run <= {result['tap_max_frames']} frames; stuck = no new max x for {result['stuck_frames']} frames.")
    if is_goal(result):
        c, real, shuf = result["criterion"], result["real"], result["shuffled"]
        met = real["reached"] >= c["real_reached_min"] and shuf["reached"] <= c["shuffled_reached_max"]
        return (f"Plan criterion (reported, not tuned): real >= {c['real_reached_min']}/{c['n']} and shuffled <= "
                f"{c['shuffled_reached_max']}/{c['n']} -> {'met' if met else 'not met'}")
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
        self.experiment_combo = QComboBox()
        self.experiment_combo.addItems(EVAL_EXPERIMENTS)
        self.experiment_combo.currentTextChanged.connect(self._relabel_button)
        self.run_button = QPushButton("")
        self.run_button.clicked.connect(self._start_eval)
        self._relabel_button("E1")
        top.addWidget(QLabel("Saved evaluation:"))
        top.addWidget(self.history_combo, 1)
        top.addWidget(self.experiment_combo)
        top.addWidget(self.run_button)
        layout.addLayout(top)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.header_label = QLabel("No evaluation saved for this project yet.")
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
            self.history_combo.addItem(f"{e.get('time', '?')[:19]}  {e.get('experiment', 'E1')}  seeds {e['seeds'][0]}-{e['seeds'][1]}")
        self.history_combo.blockSignals(False)
        if evals:
            self.history_combo.setCurrentIndex(len(evals) - 1)
            self._show(evals[-1])

    def _show_selected(self, index: int) -> None:
        if 0 <= index < len(self._evals):
            self._show(self._evals[index])

    def _relabel_button(self, experiment: str) -> None:
        a, b = EVAL_SEEDS[experiment]
        self.run_button.setText(f"Run {experiment} evaluation (seeds {a}-{b}, held-out, run once)")

    def _set_columns(self, table: QTableWidget, columns) -> None:
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(list(columns))

    def _show(self, result: dict) -> None:
        st = result["stamp"]
        if is_e2a(result):
            self.header_label.setText(
                f"E2a, scene {result['scene']['id']} ({result['scene']['scene_hash']}), seeds {result['seeds'][0]}-{result['seeds'][1]}, "
                f"{result['metric']}. Network {st['build_hash']} ({st['neurons']} neurons), calibration {st['calibration_hash']}, "
                f"senses {st.get('senses')}.")
            self._set_columns(self.summary_table, E2A_SUMMARY_COLUMNS)
            self._set_columns(self.episode_table, E2A_EPISODE_COLUMNS)
        elif is_baseline(result):
            self.header_label.setText(
                f"B11 1-1 innate baseline, scene {result['scene']['id']} ({result['scene']['scene_hash']}), seeds "
                f"{result['seeds'][0]}-{result['seeds'][1]}, max {result['max_frames']} frames. Network {st['build_hash']} "
                f"({st['neurons']} neurons), calibration {st['calibration_hash']}, senses {st.get('senses')}.")
            self._set_columns(self.summary_table, BASELINE_SUMMARY_COLUMNS)
            self._set_columns(self.episode_table, BASELINE_EPISODE_COLUMNS)
        elif is_goal(result):
            self.header_label.setText(
                f"{result['experiment']}, scene {result['scene']['id']} ({result['scene']['scene_hash']}), seeds "
                f"{result['seeds'][0]}-{result['seeds'][1]}, {result['metric']}. Network {st['build_hash']} "
                f"({st['neurons']} neurons), calibration {st['calibration_hash']}, senses {st.get('senses')}.")
            self._set_columns(self.summary_table, GOAL_SUMMARY_COLUMNS)
            self._set_columns(self.episode_table, GOAL_EPISODE_COLUMNS)
        else:
            self.header_label.setText(
                f"E1, scene {result['scene']['id']} ({result['scene']['scene_hash']}), seeds {result['seeds'][0]}-{result['seeds'][1]}, "
                f"survived = alive {result['grace_frames']} frames after the Goomba stops being a threat. Network {st['build_hash']} "
                f"({st['neurons']} neurons), calibration {st['calibration_hash']}.")
            self._set_columns(self.summary_table, SUMMARY_COLUMNS)
            self._set_columns(self.episode_table, EPISODE_COLUMNS)
        rows = summary_rows(result)
        self.summary_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                self.summary_table.setItem(r, c, QTableWidgetItem(text))
        self.criterion_label.setText(criterion_text(result))
        eps = result["episodes"]
        self.episode_table.setRowCount(len(eps))
        for r, e in enumerate(eps):
            if is_e2a(result):
                vals = [ARM_LABELS.get(e["arm"], e["arm"]), str(e["seed"]), e["outcome"], "yes" if e["cleared"] else "no", str(e["frames"]),
                        str(e["max_x"]), "yes" if e["gf_before_face"] else "no", f"{e['first_a_x']} / {e['first_a_run']}", str(e["takeoff_x"])]
            elif is_baseline(result):
                vals = [ARM_LABELS.get(e["arm"], e["arm"]), str(e["seed"]), e["outcome"], str(e["frames"]), str(e["max_x"]),
                        f"{e['goombas_jumped']} / {e['goombas_encountered']}", "-" if e["first_a_run"] is None else str(e["first_a_run"]),
                        "collected" if e["collected"] else ("released" if e["powerup_released"] else "no"),
                        f"{e['gf_output_max_hz']:.2f}", f"{e['ttmn_max_hz']:.3f}"]
            elif is_goal(result):
                vals = [ARM_LABELS.get(e["arm"], e["arm"]), str(e["seed"]), e["outcome"], "yes" if e["reached"] else "no", str(e["frames"]),
                        str(e["max_x"]), "yes" if e["gf_fired"] else "no", f"{e['gf_output_max_hz']:.2f}", f"{e['ttmn_max_hz']:.3f}",
                        f"{e['left_frames']} / {e['right_frames']} / {e['b_frames']}"]
            else:
                vals = [ARM_LABELS.get(e["arm"], e["arm"]), str(e["seed"]), e["outcome"], "yes" if e["survived"] else "no", "yes" if e["gf_before_contact"] else "no",
                        "-" if e["theta_at_gf_deg"] is None else f"{e['theta_at_gf_deg']:.1f}",
                        "-" if e["distance_at_gf_px"] is None else f"{e['distance_at_gf_px']:.0f}", str(e["a_frames"])]
            for c, text in enumerate(vals):
                self.episode_table.setItem(r, c, QTableWidgetItem(text))

    def _start_eval(self) -> None:
        if self._window.brain_runs.start_eval(experiment=self.experiment_combo.currentText()):
            self.run_button.setEnabled(False)

    def _on_eval_finished(self, result) -> None:
        self.run_button.setEnabled(True)
        if result is not None:
            self.refresh()
