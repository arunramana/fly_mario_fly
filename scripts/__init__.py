# What this file does, in plain English:
# Marks this folder as a Python package so the scripts in it can be run as
# "python -m scripts.<name>" from the repo root. It contains no code, only a
# note saying which scripts picked which settings and which ones run the
# "shuffled wiring" comparison (same neurons, connections scrambled).
"""Diagnostic, calibration, and benchmark scripts. Run from the repo root as
`python -m scripts.<name>` so the root stays on sys.path. The tune_*.py and
diag4.py scripts are the provenance docs/SCALARS.md cites for the measured
scalars; compare_controllers.py and shuffle_sweep.py are the
shuffled-connectome control (CLAUDE.md invariant 6)."""
