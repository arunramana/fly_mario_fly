"""tool/core/wiring.py -- the live/partial/not_wired status for every GUI
control that ISN'T one of config/params.py's 49 scalars (schema.py's
ControlSpecs default those to `live` directly -- C1 threads a passed
config through, C2 wired the four previously-inert groups). One source of
truth for tool/PLAN.md section 5's table; a control here is only `live`
once a test shows changing it changes telemetry (tool/PLAN.md ground rule
4 -- "no control lies").

Kept in sync with tool/PLAN.md section 5 by hand: there is no way to
derive "does the GUI exist yet" from GUI code that doesn't exist yet
(P3+). Update this file, not just the plan's table, whenever a phase
changes a control's status -- schema.py and (eventually) param_form read
THIS, not the table in the markdown.
"""

from __future__ import annotations

LIVE = "live"
PARTIAL = "partial"
NOT_WIRED = "not_wired"

# Keyed the same way schema.py paths config scalars ("group.name"), plus a
# few tool-settings-only controls that have no config/params.py home.
CONTROL_WIRING: dict[str, str] = {
    "character.player": LIVE,                # tool/core/palette.py, display-only (P4)
    "character.hunger_override": NOT_WIRED,   # C7, tool/PLAN.md P5
    "character.starting_powerup": NOT_WIRED,  # C7, tool/PLAN.md P5
    "character.arousal_pc1": NOT_WIRED,       # C9, no SPEC yet
    "enemies.smell_profile": NOT_WIRED,       # C8, tool/PLAN.md P6 (science sprint)
    "circuits.shuffle_seed": NOT_WIRED,       # C5, tool/PLAN.md P5
    "fitness.points": LIVE,                   # C4: info["score"] feeds it
    "fitness.distance": LIVE,
    "fitness.time": LIVE,
    "experiment.learning_enabled": LIVE,      # FullPolicy.event_proximal_dopamine, phase 6
    "render.frame_skip": LIVE,
    "render.record_video": LIVE,
    "render.brain_panel": LIVE,
    "render.parallel_workers": PARTIAL,       # tool/core/batch.py works (this phase); no GUI yet
    "render.live_preview_fps": NOT_WIRED,     # no live preview yet (P4)
}


def status_of(control_id: str, default: str = NOT_WIRED) -> str:
    return CONTROL_WIRING.get(control_id, default)
