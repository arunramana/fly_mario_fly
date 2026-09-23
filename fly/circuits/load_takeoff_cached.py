# What this file does, in plain English:
# Loads the take-off network (built in takeoff_circuit.py) while hiding its
# long printed build report. The slow data extraction is saved to disk the
# first time, so later loads are quick. Used by the game controller and one
# tuning script.
"""Quiet re-load of the cached takeoff (DNp01->GFC1-4->DLMn) circuit --
mirrors load_cached.py / load_steering_cached.py."""
import contextlib
import io

from fly.circuits import takeoff_circuit


def load():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = takeoff_circuit.build_full()
    return result
