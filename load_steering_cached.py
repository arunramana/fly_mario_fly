"""Quiet re-load of the cached steering circuit -- mirrors load_cached.py."""
import contextlib
import io

import steering_circuit


def load(N=steering_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = steering_circuit.build_full(N=N)
    return result
