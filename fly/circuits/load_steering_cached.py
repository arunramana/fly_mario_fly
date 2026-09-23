# What this file does, in plain English:
# Loads the steering network (built in steering_circuit.py). Its long build
# report goes to the log file, not the screen. The slow data extraction is
# saved to disk the first time, so later loads are quick. Used by the game
# controller and several tuning scripts.
"""Quiet re-load of the cached steering circuit -- mirrors load_cached.py."""
import contextlib
import io
import logging

from fly.circuits import steering_circuit

log = logging.getLogger(__name__)


def load(N=steering_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = steering_circuit.build_full(N=N)
    log.debug("steering circuit build report (N=%d):\n%s", N, buf.getvalue())
    return result
