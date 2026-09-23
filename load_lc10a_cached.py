"""Quiet re-load of the cached LC10a pursuit circuit -- mirrors load_cached.py."""
import contextlib
import io

import lc10a_pursuit_circuit


def load():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = lc10a_pursuit_circuit.build_full()
    return result
