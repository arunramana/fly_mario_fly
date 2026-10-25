"""Compliance layer: the project's rules as code.

    from fly_mario_fly.rules import declare, Route          # what plug-in files use
    python -m fly_mario_fly.rules validate                   # check every plug-in (CI runs this)
    python -m fly_mario_fly.rules list                       # print the rules

This package stays light on import (schema + guards only); the validator is imported on demand.
"""
from fly_mario_fly.rules.catalogue import RULES, Rule
from fly_mario_fly.rules.guards import RuleViolation
from fly_mario_fly.rules.schema import BUTTONS, GAME_READS, KINDS, ORIGINS, Declaration, Route, declare

__all__ = ["RULES", "Rule", "RuleViolation", "BUTTONS", "GAME_READS", "KINDS", "ORIGINS", "Declaration", "Route", "declare"]
