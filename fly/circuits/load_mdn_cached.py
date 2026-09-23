# What this file does, in plain English:
# Loads the walk-backwards network (built in mdn_circuit.py) while hiding its
# long printed build report. The slow data extraction is saved to disk the
# first time, so later loads are quick. Used by the game controller and one
# tuning script.
"""Quiet re-load of the cached MDN circuit -- mirrors load_steering_cached.py."""
import contextlib
import io

from fly.circuits import mdn_circuit


def load(N=mdn_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = mdn_circuit.build_full(N=N)
    return result
