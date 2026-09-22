"""Quiet re-load of the cached speed (DNp09) circuit -- mirrors
load_cached.py / load_steering_cached.py."""
import contextlib
import io

import speed_circuit


def load(N=speed_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = speed_circuit.build_full(N=N)
    return result
