# What this file does, in plain English:
# Loads the jump (escape) network built in circuit.py, using a cut-off of
# 60 connections, while hiding its long printed build report. The slow data
# extraction is saved to disk the first time, so later loads are quick.
# Used by both game controllers and many diagnostic scripts.
"""Quiet re-load of the cached expanded circuit -- everything's already on
disk, this just silences the verbose build prints for fast iteration."""
import contextlib
import io

from fly.connectome import circuit


def load(N=60):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = circuit.build_expanded(N=N)
    return result
