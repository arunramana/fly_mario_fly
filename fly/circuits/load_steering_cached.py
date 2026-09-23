# What this file does, in plain English:
# Loads the steering network (built in steering_circuit.py) while hiding its
# long printed build report. The slow data extraction is saved to disk the
# first time, so later loads are quick. Used by the game controller and
# several tuning scripts.
"""Quiet re-load of the cached steering circuit -- mirrors load_cached.py."""
import contextlib
import io

from fly.circuits import steering_circuit


def load(N=steering_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = steering_circuit.build_full(N=N)
    return result
