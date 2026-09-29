# What this file does, in plain English:
# Decides when the learning centre gets a "reward" or "punishment" signal
# (dopamine, the chemical that tells it something good or bad happened):
# hitting a ? block or stomping an enemy is reward, dying is punishment,
# each sent at full strength at the moment it happens. Turning into Super
# Mario (eating a mushroom) is a reward too, but only when asked for. The game
# controller always uses the death signal but uses the reward part only when
# asked.
"""fly/plasticity/dopamine.py -- event-proximal dopamine routing.

A KC->MBON synaptic tag lasts ~1-2s and is negligible by 6s (Handler et al.
2019), but Mario's decision-to-consequence gap runs 4-9s. So dopamine is
delivered at the event itself, as the real animal receives it
(docs/TRACE_BIOLOGY.md).

Never wire this to `sim/fitness.py`: fitness is episode-level, for judging
a run afterwards; dopamine is event-level and the only reward the mushroom
body sees. Connecting them brings back the delayed credit the tag cannot
bridge.
"""

from __future__ import annotations

from fly.network import dynamics


def event_dopamine(qblock_hit: bool, stomp: bool, died: bool,
                   powerup: bool = False) -> tuple[float, float]:
    """Routes RAM-decodable events to the two DAN compartments
    (SPEC_mushroom_body.md section 3): a `?` block hit or a stomp -> PAM
    (appetitive), death -> PPL1/PPM (aversive). `powerup` (Mario just became
    Super, RAM 0x0756 rose from 0) is the same appetitive pulse
    (docs/SPEC_learning_v2.md section 4); the caller passes it only when the
    power-up reward is switched on. Magnitude is
    `dynamics.CLIP` either way, a one-shot event rather than a new scalar.

    Returns `(pam_dopamine, punish_dopamine)`. `died` only comes from
    FullPolicy.on_step() after the episode ends, so it never coincides with
    a same-frame reward.
    """
    pam = dynamics.CLIP if (qblock_hit or stomp or powerup) else 0.0
    punish = dynamics.CLIP if died else 0.0
    return pam, punish
