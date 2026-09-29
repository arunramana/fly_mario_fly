"""tool/core/fps_meter.py -- rolling rates for the live-preview readout: how fast
the simulation is producing frames versus how fast the UI actually draws them,
so a slowdown can be blamed on the right one."""

from __future__ import annotations

import time
from collections import deque


class FpsMeter:
    def __init__(self, window_s: float = 1.0, clock=time.perf_counter):
        self.window_s = window_s
        self._clock = clock
        self._sim: deque = deque()    # (time, sim frame number)
        self._shown: deque = deque()  # time of each drawn frame

    def reset(self) -> None:
        self._sim.clear()
        self._shown.clear()

    def sim_frame(self, frame: int) -> None:
        self._sim.append((self._clock(), frame))

    def shown_frame(self) -> None:
        self._shown.append(self._clock())

    def rates(self) -> tuple[float, float]:
        """(simulated frames/s, displayed frames/s) over the recent window."""
        now = self._clock()
        while self._sim and now - self._sim[0][0] > self.window_s:
            self._sim.popleft()
        while self._shown and now - self._shown[0] > self.window_s:
            self._shown.popleft()
        sim = 0.0
        if len(self._sim) >= 2 and self._sim[-1][0] > self._sim[0][0]:
            sim = (self._sim[-1][1] - self._sim[0][1]) / (self._sim[-1][0] - self._sim[0][0])
        shown = len(self._shown) / self.window_s
        return sim, shown
