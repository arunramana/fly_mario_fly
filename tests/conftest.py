"""Set BLAS/OpenMP thread counts before ANY test module (or numpy) gets
imported -- pytest imports conftest.py before collecting test_*.py files,
which is earlier than run_steering.py's own `os.environ.setdefault(...)`
of the same three variables.

Found this the hard way (REFACTOR_PLAN.md phase 2): `pytest tests/` (all
three files together) produced a bit-level (~1 part in 1e16, one float's
last digit) divergence from `pytest tests/test_golden.py` alone, only when
tests/test_entities.py's numpy usage ran first and imported numpy before
run_steering.py did. Once ANY module imports numpy first, the underlying
BLAS library appears to latch its thread count from the ambient (at that
point still unset) environment; run_steering.py's own `setdefault` a few
imports later is too late to change a decision BLAS already made. Verified
directly: exporting these three variables in the shell before launching
pytest at all made the divergence disappear. This module is the same fix,
without depending on the caller's shell.

Not a behaviour bug in the circuits -- the golden CSVs are still exactly
reproducible, this just makes that reproducibility independent of test
file import order, which phase 0 never had a second test file to expose.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
