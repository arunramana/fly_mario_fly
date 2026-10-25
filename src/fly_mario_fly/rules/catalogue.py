"""The project's rules as data: one place that says what they are and what enforces each of them.

Section "Do / Don't" of docs/CLOUD_SESSION_BRIEF.md, in code. `python -m fly_mario_fly.rules list` prints it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str          # "do" | "dont" | "declare"
    text: str
    enforced_by: str   # where it is checked (validator check, runtime guard, test)


RULES = (
    Rule("D1", "do", "The fly makes every decision.",
         "R-ACTION-SOURCE (validator), GuardedRates + button check (runtime), tests/test_rules_guards.py"),
    Rule("D2", "do", "Read the game's memory to work out what the fly senses.",
         "objects find() read RAM only; senses see ObjectInstances, never the emulator (tests/test_boundaries.py)"),
    Rule("D3", "do", "Invent cues the fly can react to: a sense turns an object into drive on a declared real route.",
         "R-SENSE-ROUTE (validator), check_sense_output (runtime)"),
    Rule("D4", "do", "Add dials that set how strong each sense and cue is; dials are all evolution may tune.",
         "R-DIALS (validator); evolve/genome.py only reads evolvable KnobSpecs"),
    Rule("N1", "dont", "Edit the fly's wiring. No neuroevolution: connectome weights are read-only.",
         "frozen weights + fingerprint check (runtime), R-NO-WEIGHT-WRITES (static scan)"),
    Rule("N2", "dont", "Fire the fly's neurons directly: only declared input groups can be driven.",
         "Brain.drive / Brain.advance guards (runtime), R-NO-DIRECT-DRIVE (static scan)"),
    Rule("N3", "dont", "Let our code decide an action for the fly: buttons come from motor or descending neuron rates.",
         "R-ACTION-SOURCE (validator), GuardedRates (runtime)"),
    Rule("S1", "declare", "Every sense, action, object, character, shape, scene and mechanism declares its origin: "
         "'fly' (teal, real wiring) or 'invented' (orange).", "R-DECLARED (validator)"),
    Rule("S2", "declare", "A 'fly' item cites the real route and cell types it rides on.", "R-FLY-ROUTE (validator)"),
)
