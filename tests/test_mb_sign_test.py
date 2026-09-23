"""
The sign test: does the rule flip sign with pairing order? Exercises the
real fly.plasticity.three_factor depress()/update_eligibility():

  FORWARD:  KC fires, THEN dopamine arrives (a few frames later).
  BACKWARD: dopamine arrives, THEN KC fires (a few frames later).

In the real animal forward pairing depresses and backward pairing
potentiates (Handler et al. 2019, docs/TRACE_BIOLOGY.md). This project's
rule (SPEC_mushroom_body.md section 4, depression only) depresses on
forward pairing and produces NO significant change on backward pairing. A
deliberate simplification -- valence is modelled by depressing a different
MBON population, not by flipping sign -- so this test asserts what the rule
does and does not claim Handler et al.'s result.
"""
from __future__ import annotations

import numpy as np

from fly.plasticity.three_factor import depress, update_eligibility

TAU = 60.0            # frames, docs/TRACE_BIOLOGY.md's own measured range
LEARNING_RATE = 0.001  # config.params.MushroomBodyParams.learning_rate
DOPAMINE_MAGNITUDE = 50.0  # dynamics.CLIP


def _run_protocol(kc_fire_frame: int, dopamine_frame: int, n_frames: int = 20) -> float:
    """One KC, one MBON, one real synapse of weight 1.0. Returns the net
    change in W after `n_frames` (positive = potentiation, negative =
    depression, ~0 = no significant plasticity)."""
    W = np.array([[1.0]])
    elig = np.zeros(1)
    for t in range(n_frames):
        kc_active = np.array([1.0]) if t == kc_fire_frame else np.array([0.0])
        elig = update_eligibility(elig, kc_active, TAU)
        if t == dopamine_frame:
            dopamine = np.array([DOPAMINE_MAGNITUDE])
            W = depress(W, dopamine, elig, LEARNING_RATE)
    return float(W[0, 0] - 1.0)


def test_forward_pairing_depresses():
    """KC fires at t=0, dopamine arrives at t=5 (well inside the 60-120
    frame trace window) -- the eligibility trace still carries the KC
    firing, so this pairing should produce real depression."""
    dW = _run_protocol(kc_fire_frame=0, dopamine_frame=5)
    assert dW < 0, f"forward pairing (KC then DA) should depress the synapse, got dW={dW}"


def test_backward_pairing_does_not_potentiate():
    """Dopamine arrives at t=0 (before any KC activity), KC fires at t=5.
    The real fly (Handler et al. 2019) potentiates here -- opposite sign
    from forward pairing. This project's depression-only rule cannot
    produce a positive dW at all (there is no branch in depress() that
    ever adds weight), so the honest assertion is "no significant
    change", not "potentiates"."""
    dW = _run_protocol(kc_fire_frame=5, dopamine_frame=0)
    assert abs(dW) < 1e-9, (
        f"expected ~zero change (no eligibility yet when dopamine arrived), got dW={dW}"
    )


def test_the_rule_does_not_flip_sign_with_order():
    """THE finding this step exists to check, stated as its own explicit
    assertion rather than left implicit in the two tests above: forward
    and backward pairing do NOT produce opposite-sign plasticity under
    this project's current rule. This is the honest result of the sign
    test the phase 6 prompt asked for -- reported as a fact about the
    implementation, not a bug silently patched over before anyone saw it.
    See SPEC_mushroom_body.md section 4 ("depression only, both
    directions") for the earlier sprint's own stated reasoning, and
    docs/RUNS.md's phase 6 entry for what this means for the mechanism
    going forward."""
    dW_forward = _run_protocol(kc_fire_frame=0, dopamine_frame=5)
    dW_backward = _run_protocol(kc_fire_frame=5, dopamine_frame=0)
    same_sign_or_zero = (dW_forward <= 0) and (dW_backward <= 0)
    assert same_sign_or_zero, (
        "if this assertion ever fails, the rule started potentiating on "
        "backward pairing -- which would mean it now DOES match Handler "
        "et al.'s bidirectional finding and this whole test (and its "
        "docstring's conclusion) needs rewriting, not just re-asserting"
    )


def test_magnitude_scales_with_learning_rate_not_isi():
    """A sanity check that the depression magnitude here is governed by
    LEARNING_RATE and the eligibility trace's own decay, not by some
    accidental ISI-dependent term hiding in the arithmetic -- forward
    pairing at a short ISI (dopamine arrives while eligibility is still
    high) should depress MORE than at a long ISI (eligibility has mostly
    decayed by the time dopamine arrives), a graded difference in
    MAGNITUDE, still the same sign both times."""
    dW_short_isi = _run_protocol(kc_fire_frame=0, dopamine_frame=2)
    dW_long_isi = _run_protocol(kc_fire_frame=0, dopamine_frame=15)
    assert dW_short_isi < 0 and dW_long_isi < 0
    assert abs(dW_short_isi) > abs(dW_long_isi), (
        "a short ISI should depress more than a long one (more eligibility "
        "left when dopamine arrives) -- both are still depression, this "
        "just confirms the trace's own decay is doing something"
    )
