"""Quiet re-load of the cached expanded circuit -- everything's already on
disk, this just silences the verbose build prints for fast iteration."""
import contextlib
import io

import circuit


def load(N=60):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = circuit.build_expanded(N=N)
    return result
