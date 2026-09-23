# What this file does, in plain English:
# Loads the second-escape-route network (built in dnp02_circuit.py) while
# hiding its long printed build report. The slow data extraction is saved to
# disk the first time, so later loads are quick. Used by the game controller
# and one tuning script.
"""Quiet re-load of the cached DNp02 circuit -- mirrors load_mdn_cached.py."""
import contextlib
import io

from fly.circuits import dnp02_circuit


def load(N=dnp02_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = dnp02_circuit.build_full(N=N)
    return result
