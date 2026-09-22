"""Quiet re-load of the cached mushroom-body circuit -- mirrors load_dnp02_cached.py."""
import contextlib
import io

import mushroom_body_circuit


def load():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = mushroom_body_circuit.build_full()
    return result
