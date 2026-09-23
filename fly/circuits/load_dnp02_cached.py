"""Quiet re-load of the cached DNp02 circuit -- mirrors load_mdn_cached.py."""
import contextlib
import io

from fly.circuits import dnp02_circuit


def load(N=dnp02_circuit.N_THRESHOLD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = dnp02_circuit.build_full(N=N)
    return result
