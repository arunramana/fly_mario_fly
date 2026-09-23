"""Quiet re-load of the cached MDN circuit -- mirrors load_steering_cached.py."""
import contextlib
import io

from fly.circuits import mdn_circuit


def load(N=mdn_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = mdn_circuit.build_full(N=N)
    return result
