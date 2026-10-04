"""tool/ui/brain_runs.py -- docs/SPEC_tool_phase2.md section 7: the window's brain-path runs.

Owns the child processes for one E1 episode (streamed to the Run tab's player, i.e. Watch) and for the 20-seed
real-vs-shuffled evaluation (shown on the Results tab). The legacy Play/batch/train machinery in main_window.py is
untouched; this sits beside it and writes to the same run store, so a brain run is played and listed like any other run.
"""

from __future__ import annotations

import multiprocessing as mp
import os

from PySide6.QtCore import QObject, QTimer, Signal

from tool.core.brain_runner import (brain_run_slug, episode_of, load_sense_settings, run_brain_eval_streaming,
                                    run_brain_streaming, write_brain_run_note)
from tool.core.run_store import list_runs, next_run_number, record_run


class BrainRunController(QObject):
    eval_finished = Signal(object)        # the evaluation dict, or None on failure
    eval_status = Signal(str)

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._process = self._queue = self._stop = None
        self._meta: dict | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._poll_run)
        self._eval_process = self._eval_queue = None
        self._eval_timer = QTimer(self)
        self._eval_timer.setInterval(1000)
        self._eval_timer.timeout.connect(self._poll_eval)

    # ---- one episode, watched ------------------------------------------------------------------------------------
    def run_active(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def eval_active(self) -> bool:
        return self._eval_process is not None and self._eval_process.is_alive()

    def active(self) -> bool:
        return self.run_active() or self.eval_active()

    def start_run(self, seed: int, shuffled: bool, shuffle_seed: int = 1, experiment: str = "E1", class_shuffle: bool = False) -> bool:
        w = self._window
        if self.active() or (w._process is not None and w._process.is_alive()) or w.training_active():
            w.statusBar().showMessage("Something is already running -- cancel it first.", 5000)
            return False
        mode = "shuffled_class" if class_shuffle else "shuffled"
        arm = mode if shuffled else "real"
        number = next_run_number(w.project.name)
        slug = brain_run_slug(number, arm, seed, experiment)
        ctx = mp.get_context("spawn")
        self._queue, self._stop = ctx.Queue(), ctx.Event()
        self._meta = {"number": number, "slug": slug, "seed": seed, "experiment": experiment}
        settings = load_sense_settings(w.project.name).to_dict()      # the Mechanisms tab's settings travel with the run
        self._process = ctx.Process(target=run_brain_streaming, args=(
            w.project.name, slug, seed, shuffle_seed if shuffled else None, self._queue, self._stop, experiment, settings, mode))
        self._process.start()
        w.run_tab.set_running(True)
        w.run_tab.progress.setValue(0)
        w.tabs.setCurrentWidget(w.run_tab)         # Watch
        self._timer.start()
        return True

    def cancel(self) -> None:
        if self._stop is not None and self.run_active():
            self._stop.set()

    def _poll_run(self) -> None:
        if self._queue is None:
            return
        latest, terminal = None, None
        while not self._queue.empty():
            message = self._queue.get_nowait()
            if message[0] == "frame":
                latest = message
            else:
                terminal = message
                break
        run_tab = self._window.run_tab
        if latest is not None:
            run_tab.preview.show_frame(latest[1], latest[2])
            from brain.e1 import E1_MAX_FRAMES
            from brain.baseline import BASELINE_MAX_FRAMES
            from brain.goal_eval import MAX_FRAMES
            exp = (self._meta or {}).get("experiment", "E1")
            run_tab.set_progress(latest[2].get("frame", 0), E1_MAX_FRAMES if exp == "E1" else {**MAX_FRAMES, "B11": BASELINE_MAX_FRAMES}[exp])
        if terminal is None:
            return
        self._timer.stop()
        if self._process is not None:
            self._process.join(timeout=5)
        self._process = None
        run_tab.set_running(False)
        if terminal[0] == "error":
            run_tab.show_result(f"Brain run failed: {terminal[1]}", is_error=True)
            self._window.statusBar().showMessage("Brain run failed", 10_000)
            return
        self._finish(terminal[1], terminal[2])

    def _finish(self, info: dict, spec: dict) -> None:
        w, m = self._window, self._meta
        run_tab = w.run_tab
        run_tab.progress.setValue(100)
        record_run(w.project.name, m["number"], m["slug"], m["seed"], info, spec)
        write_brain_run_note(w.project.name, m["number"], m["slug"], m["seed"], info)
        run_tab.refresh_history(list_runs(w.project.name))
        run_tab.select_run(m["number"])
        w.load_history_run({"number": m["number"], "slug": m["slug"], "seed": m["seed"], "summary": info, "run_spec": spec})
        e = episode_of(info)
        if m.get("experiment", "E1") == "E1":
            text = (f"Run #{m['number']} (E1, {e['arm']}): {e['outcome']}, survived {e['survived']}, GF before contact "
                    f"{e['gf_before_contact']}, theta at GF "
                    f"{'none' if e['theta_at_gf_deg'] is None else format(e['theta_at_gf_deg'], '.1f') + ' deg'}")
        else:
            text = (f"Run #{m['number']} ({m['experiment']}, {e['arm']}): {e['outcome']}, reached {e['reached']}, GF fired "
                    f"{e['gf_fired']}, GF output max {e['gf_output_max_hz']:.2f} Hz, TTMn max {e['ttmn_max_hz']:.3f} Hz")
        run_tab.show_result(text)
        w.statusBar().showMessage(text, 10_000)

    # ---- the 20-seed evaluation ------------------------------------------------------------------------------------
    def start_eval(self, n: int | None = None, seed0: int | None = None, experiment: str = "E1") -> bool:
        if self.active():
            return False
        ctx = mp.get_context("spawn")
        self._eval_queue = ctx.Queue()
        self._eval_process = ctx.Process(target=run_brain_eval_streaming, args=(
            self._window.project.name, self._eval_queue, max(1, (os.cpu_count() or 2) // 2), n, seed0, experiment,
            load_sense_settings(self._window.project.name).to_dict()))
        self._eval_process.start()
        self._eval_timer.start()
        arms = ("real, shuffled and the GF-lesion control" if experiment == "E1"
                else "real, degree-preserving shuffled, class-preserving shuffled and "
                + ("real with the landmark off" if experiment == "E0" else "real with pursuit off"))
        if experiment == "B11":
            arms = "real, degree-preserving shuffled and class-preserving shuffled; a baseline, no pass/fail"
        self._eval_experiment = experiment
        self.eval_status.emit(f"{experiment} evaluation running ({arms}, 20 seeds each)...")
        return True

    def _poll_eval(self) -> None:
        if self._eval_queue is None or self._eval_queue.empty():
            return
        kind, payload = self._eval_queue.get_nowait()
        self._eval_timer.stop()
        self._eval_process.join(timeout=5)
        self._eval_process = None
        if kind == "done":
            self.eval_status.emit(f"{getattr(self, '_eval_experiment', 'E1')} evaluation finished.")
            self.eval_finished.emit(payload)
        else:
            self.eval_status.emit(f"{getattr(self, '_eval_experiment', 'E1')} evaluation failed: {payload[:300]}")
            self.eval_finished.emit(None)
