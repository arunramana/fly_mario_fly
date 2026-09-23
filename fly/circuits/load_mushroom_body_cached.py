# What this file does, in plain English:
# Loads the learning-centre network (built in mushroom_body_circuit.py) while
# hiding its long printed build report. The slow data extraction is saved to
# disk the first time, so later loads are quick. Used by the game controller.
"""Quiet re-load of the cached mushroom-body circuit -- mirrors load_dnp02_cached.py."""
import contextlib
import io

from fly.circuits import mushroom_body_circuit


def load():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = mushroom_body_circuit.build_full()
    return result
