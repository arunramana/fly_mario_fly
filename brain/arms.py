# What this file does, in plain English:
# One place that decides which control arms a routine evaluation runs. The degree-preserving
# shuffled network ("shuffled") has failed 0/20 on every experiment, so a routine run leaves it
# out; it comes back with a flag (or an explicit --arms) at the release boundary and after a
# change to the stimulus layer, the network or the calibration. Nothing here touches a brain.
"""brain/arms.py -- docs/SPEC_fast_iteration.md step 1.

Re-run the degree shuffle (`--with-degree-shuffle`, alias `--release`) when any of these changes:
  * the stimulus layer: brain/perception.py, brain/obstacles.py, the mechanisms' encoding (brain/mechanisms.py)
  * the network hash (a rebuilt network) or the calibration hash
  * at the release boundary
An explicit `--arms` or `arms=` argument is always honoured exactly as given.
"""

from __future__ import annotations

DEGREE_SHUFFLE_ARM = "shuffled"
FLAGS = ("--with-degree-shuffle", "--release")


def routine_arms(full: tuple[str, ...], with_degree_shuffle: bool = False) -> tuple[str, ...]:
    """`full` without the degree-shuffle arm, unless it is asked for."""
    return tuple(a for a in full if with_degree_shuffle or a != DEGREE_SHUFFLE_ARM)


def resolve_arms(arms, full: tuple[str, ...], with_degree_shuffle: bool = False) -> tuple[str, ...]:
    """An explicit `arms` wins; None means the routine default (or the full set when the degree shuffle is requested)."""
    return tuple(arms) if arms else routine_arms(full, with_degree_shuffle)


def add_flag(parser) -> None:
    """The --with-degree-shuffle / --release switch every harness CLI shares."""
    parser.add_argument(*FLAGS, dest="with_degree_shuffle", action="store_true",
                        help="also run the degree-preserving shuffled arm (release boundary, or after a change to the "
                             "stimulus layer / network hash / calibration); routine runs leave it out")
