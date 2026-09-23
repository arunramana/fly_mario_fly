"""fly/plasticity/dopamine.py -- REFACTOR_PLAN.md phase 6 step 3:
event-proximal dopamine routing.

docs/TRACE_BIOLOGY.md's whole reason to exist: a KC->MBON synaptic tag is
significant for ~1-2s and negligible by 6s (Handler et al. 2019), while
Mario's own decision-to-consequence gap runs 4-9s (025's cascade
measurement) -- too long for episode-end credit assignment to ever reach
the decision that caused it. The fix is not a longer trace, it's
delivering dopamine at the event, immediately, the way the real animal
actually receives it (sugar on the proboscis now, not "you died nine
seconds later").

`DopamineSignal` is not `Fitness` (sim/fitness.py) and the two must never
be wired together -- `Fitness` is episode-level, for evaluating a run
after the fact; this is event-level, the only thing the mushroom body
ever sees. Connecting them would reintroduce exactly the delayed-credit
problem the biology says the eligibility tag cannot solve.
"""

from __future__ import annotations

from fly.network import dynamics


def event_dopamine(qblock_hit: bool, stomp: bool, died: bool) -> tuple[float, float]:
    """Routes the three real, RAM-decodable event classes to the two DAN
    compartments this mushroom body's dopaminergic population is already
    split into (mb_pam_reach / mb_punish_reach, SPEC_mushroom_body.md
    section 3): a `?` block hit or a stomp -> PAM (appetitive); death ->
    PPL1/PPM (aversive). Reuses `dynamics.CLIP` for magnitude on both
    sides -- the same constant punishment already used before this phase,
    not a new invented scalar (an event either happened this frame or it
    didn't, so a fixed one-shot magnitude fits the biology better than
    accumulating a continuous quantity ever did).

    Returns `(pam_dopamine, punish_dopamine)`. At most one is nonzero in
    any one call this circuit currently makes: `died` is only ever True
    from `FullPolicy.on_step()`, after the episode has already ended, so
    it never coincides with a same-frame qblock_hit/stomp call from
    `act()`.
    """
    pam = dynamics.CLIP if (qblock_hit or stomp) else 0.0
    punish = dynamics.CLIP if died else 0.0
    return pam, punish
