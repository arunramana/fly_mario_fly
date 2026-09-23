# What this file does, in plain English:
# Loads the walk-forward network (built in speed_circuit.py). Its long build
# report goes to the log file, not the screen. The slow data extraction is
# saved to disk the first time, so later loads are quick. Used by the game
# controller and one tuning script.
"""Quiet re-load of the cached speed (DNp09) circuit -- mirrors
load_cached.py / load_steering_cached.py."""
import contextlib
import io
import logging

from fly.circuits import speed_circuit

log = logging.getLogger(__name__)


def load(N=speed_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = speed_circuit.build_full(N=N)
    log.debug("speed circuit build report (N=%d):\n%s", N, buf.getvalue())
    return result
