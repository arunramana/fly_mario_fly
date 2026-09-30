# What this file does, in plain English:
# Loads the Down/Up network built in posture_circuit.py, sending its long
# build report to the log instead of the screen (same as the other loaders).
"""Quiet re-load of the cached posture circuit -- mirrors load_mdn_cached.py."""
import contextlib
import io
import logging

from fly.circuits import posture_circuit

log = logging.getLogger(__name__)


def load(N=posture_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = posture_circuit.build_full(N=N)
    log.debug("posture circuit build report (N=%d):\n%s", N, buf.getvalue())
    return result
