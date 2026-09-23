# What this file does, in plain English:
# Loads the walk-forward network (built in speed_circuit.py) while hiding its
# long printed build report. The slow data extraction is saved to disk the
# first time, so later loads are quick. Used by the game controller and one
# tuning script.
"""Quiet re-load of the cached speed (DNp09) circuit -- mirrors
load_cached.py / load_steering_cached.py."""
import contextlib
import io

from fly.circuits import speed_circuit


def load(N=speed_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = speed_circuit.build_full(N=N)
    return result
