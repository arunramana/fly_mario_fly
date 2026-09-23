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
