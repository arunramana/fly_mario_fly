# What this file does, in plain English:
# Loads the walk-backwards network (built in mdn_circuit.py). Its long build
# report goes to the log file, not the screen. The slow data extraction is
# saved to disk the first time, so later loads are quick. Used by the game
# controller and one tuning script.
"""Quiet re-load of the cached MDN circuit -- mirrors load_steering_cached.py."""
import contextlib
import io
import logging

from fly.circuits import mdn_circuit

log = logging.getLogger(__name__)


def load(N=mdn_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = mdn_circuit.build_full(N=N)
    log.debug("MDN circuit build report (N=%d):\n%s", N, buf.getvalue())
    return result
