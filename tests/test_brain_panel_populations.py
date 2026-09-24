# What this file does, in plain English:
# Checks that the live-brain panel actually knows where MDN and the
# mushroom body's neurons sit in the real connectome -- a real gap
# tool/SPEC_ui_retro.md section 8 called out (their circuit cards would
# otherwise be blank silhouettes).
"""render/brain_panel.py: MDN and mushroom-body (KC/MBON/DAN) soma
positions, extended from connectome somaLocation (tool/SPEC_ui_retro.md
section 8's own stated gap -- previously only LC4/LPLC2/DNp01/TTMn/
DNa01/DNa02/DNp09/DLMn had real positions)."""
from __future__ import annotations

from render import brain_panel


def test_new_populations_have_real_soma_positions():
    cache = brain_panel._build()
    for pop in ("MDN", "KC", "MBON", "DAN"):
        u, v = cache["pop"][pop]
        assert len(u) > 0, f"{pop} has no soma positions -- brain_panel's mask for it is wrong"


def test_mdn_count_matches_the_connectome_circuit_extraction():
    """fly/circuits/mdn_circuit.py's own CORE_TYPES = ["MDN"] -- the same
    selection this module now uses, so the two must agree."""
    cache = brain_panel._build()
    u, _v = cache["pop"]["MDN"]
    assert len(u) == 4  # confirmed directly against the annotations feather


def test_mushroom_body_counts_are_close_to_the_circuit_extraction_s_expected():
    """fly/circuits/mushroom_body_circuit.py asserts exactly EXPECTED_KC=4064/
    EXPECTED_MBON=97/EXPECTED_DAN=354 bodies (any body, not just ones with a
    somaLocation) -- this module additionally requires somaLocation.notna(),
    so a handful fewer is expected, not a mismatch."""
    cache = brain_panel._build()
    kc_u, _ = cache["pop"]["KC"]
    mbon_u, _ = cache["pop"]["MBON"]
    dan_u, _ = cache["pop"]["DAN"]
    assert 4000 <= len(kc_u) <= 4064
    assert 90 <= len(mbon_u) <= 97
    assert len(dan_u) == 354  # every DAN body in this connectome has a somaLocation


def test_highlight_populations_renders_every_circuit_card_s_population_set():
    """tool/SPEC_ui_retro.md section 8's new highlight_populations(): a
    static, full-brightness render for each of the six circuit cards --
    must not crash and must return the brain-only canvas size."""
    from render.brain_panel import BRAIN_W, BRAIN_H
    for pops in (["LC4", "LPLC2", "DNp01", "TTMn"], ["DNa01", "DNa02"],
                 ["DNp09"], ["DLMn"], ["MDN"], ["KC", "MBON", "DAN"]):
        image = brain_panel.highlight_populations(pops)
        assert image.size == (BRAIN_W, BRAIN_H)
