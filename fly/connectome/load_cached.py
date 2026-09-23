# What this file does, in plain English:
# Loads the jump (escape) network built in circuit.py, using a cut-off of
# 60 connections. Its long build report goes to the log file, not the
# screen. The slow data extraction is saved to disk the first time, so later
# loads are quick. Used by both game controllers and many diagnostic scripts.
"""Quiet re-load of the cached expanded circuit -- everything's already on
disk, this just moves the verbose build prints to the DEBUG log."""
import contextlib
import io
import logging

from fly.connectome import circuit

log = logging.getLogger(__name__)


def load(N=60):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = circuit.build_expanded(N=N)
    log.debug("jump circuit build report (N=%d):\n%s", N, buf.getvalue())
    return result
