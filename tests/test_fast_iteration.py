# What this file does, in plain English:
# Checks the fast-iteration changes of docs/SPEC_fast_iteration.md: routine runs leave the degree-shuffle arm out (and the
# flag or an explicit --arms brings it back), the early stops of the E1 episode are the verdict's own stops, and the pruned
# network view gives bit-identical outputs to the full network.
"""tests/test_fast_iteration.py -- docs/SPEC_fast_iteration.md. The episode and prune tests need the cached network."""

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pytest

from brain import arms, baseline, builder, dose_response, e1, e2a, evaluation, goal_eval
from brain.calibration import CALIBRATION_FILE

needs_net = pytest.mark.skipif(not builder.default_path().exists() or not CALIBRATION_FILE.exists(),
                               reason="unified network / calibration not built")


# ---- step 1: the degree-shuffle arm is not a routine arm ---------------------------------------------------------------
def test_routine_arms_drop_only_the_degree_shuffle_and_the_flag_restores_it():
    full = ("real", "shuffled", "shuffled_class", "lesion_gf")
    assert arms.routine_arms(full) == ("real", "shuffled_class", "lesion_gf")
    assert arms.routine_arms(full, True) == full
    assert arms.resolve_arms(("shuffled", "real"), full) == ("shuffled", "real")      # explicit --arms is honoured
    assert arms.resolve_arms(None, full, True) == full


@pytest.mark.parametrize("mod", [e1, e2a, baseline])
def test_cli_passes_no_arms_and_the_flag_through(mod, monkeypatch):
    seen = []
    monkeypatch.setattr(mod, "run_eval", lambda *a, **k: seen.append((a, k)) or {})
    monkeypatch.setattr(mod, "format_eval", lambda r: "")
    for flags, want in (([], False), (["--with-degree-shuffle"], True), (["--release"], True)):
        mod.main(["--n", "1", *flags])
        a, k = seen[-1]
        assert (a[4] if len(a) > 4 else k.get("arms")) is None             # no explicit arms: the harness picks the routine set
        assert (a[5] if len(a) > 5 else k.get("with_degree_shuffle", False)) is want
    mod.main(["--n", "1", "--arms", "real"])
    a, k = seen[-1]
    assert (a[4] if len(a) > 4 else k.get("arms")) == ("real",)


def test_every_harness_exposes_the_flag_and_routine_defaults():
    assert e2a.ALL_ARMS == ("real", "shuffled", "shuffled_class", "real_no_obstacle")
    assert arms.routine_arms(e2a.ALL_ARMS) == ("real", "shuffled_class", "real_no_obstacle")
    assert goal_eval.default_arms("E0") == ("real", "shuffled_class", "real_no_landmark")
    assert arms.routine_arms(dose_response.DOSE_ARMS) == ("real",)
    import inspect
    for mod in (e1, e2a, baseline):
        assert "with_degree_shuffle" in inspect.signature(mod.run_eval).parameters
    assert "with_degree_shuffle" in inspect.signature(goal_eval.run_eval).parameters
    assert "with_degree_shuffle" in inspect.signature(dose_response.run_dose_response).parameters
    assert "with_degree_shuffle" in inspect.signature(evaluation.run_eval).parameters


def test_the_results_tab_criterion_line_tolerates_a_missing_degree_shuffle_arm():
    pytest.importorskip("PySide6")
    from tool.ui.tabs.results import criterion_text
    base = {"criterion": dict(e1.CRITERION), "real": {"survived": 17, "n": 20}}
    assert "met" in criterion_text(base) and "not run" in criterion_text(base)
    base["shuffled"] = {"survived": 0, "n": 20}
    assert "not run" not in criterion_text(base)


# ---- step 2: the episodes already end when the verdict is final -----------------------------------------------------------
@needs_net
def test_e1_ends_at_death_or_resolved_plus_grace_and_a_later_cap_changes_nothing():
    res, _, _ = e1.run_e1_episode(9600)
    assert res.died or res.resolved_frame is not None and res.frames == res.resolved_frame + e1.E1_GRACE_FRAMES
    again, _, _ = e1.run_e1_episode(9600, max_frames=res.frames + 200)          # more room: the same decided-state stop
    assert asdict(again) == asdict(res)
    assert res.frames < e1.E1_MAX_FRAMES


@needs_net
def test_e2a_ends_at_the_clear_and_a_later_cap_changes_nothing():
    res, _, _ = e2a.run_e2a_episode(9600)
    assert res.outcome in e2a.END_REASONS and res.outcome != "timeout"
    if res.cleared:
        assert res.frames == res.cleared_frame
    again, _, _ = e2a.run_e2a_episode(9600, max_frames=res.frames + 200)
    assert asdict(again) == asdict(res)


# ---- step 3: the pruned view is the same run ---------------------------------------------------------------------------------
def _hash(res, rows) -> str:
    h = hashlib.sha256(json.dumps(asdict(res), sort_keys=True, default=str).encode())
    for r in rows:
        h.update(json.dumps(r, sort_keys=True, default=repr).encode())
    return h.hexdigest()


@needs_net
def test_the_prune_keeps_every_ancestor_of_what_is_read_and_reports_the_full_hash():
    from brain.pruned import READ_POPULATIONS, prune_network
    net = builder.load_or_build()
    view = prune_network(net)
    assert view.build_hash() == net.build_hash() and view.view.n_full == net.n_neurons
    assert 0 < view.n_neurons <= net.n_neurons
    for p in READ_POPULATIONS:                                    # nothing that is read was removed
        assert len(view.pops[p]) == len(net.pops[p])
    # the noise-driven populations that reach the outputs through the wiring are ancestors, so they must stay
    for p in ("ORN", "THERMO", "KC", "MBON"):
        assert len(view.pops[p]) == len(net.pops[p]), p
    keep = view.view.keep
    dropped = np.setdiff1d(np.arange(net.n_neurons), keep)
    assert net.W[keep][:, dropped].nnz == 0                       # no dropped neuron drives a kept one (the exactness condition)
    with pytest.raises(ValueError):
        view.shuffled(1)


@needs_net
def test_a_pruned_brain_gives_bit_identical_frames_on_a_synthetic_stimulus():
    from brain.brain import Brain
    from brain.calibration import Calibration
    from brain.pruned import prune_network
    net, cal = builder.load_or_build(), Calibration.load()

    def trace(n):
        b = Brain(n, cal)
        b.reset(5)
        ids = b.sensory_ids[:60]
        out = []
        for f in range(25):
            b.stimulate(ids, 0.5 if f > 8 else 0.0)
            r = b.step_frame()
            out.append(list(r.rates.values()) + [r.gf_membrane, float(r.gf_spiked)])
        return np.array(out)
    assert np.array_equal(trace(net), trace(prune_network(net)))


@needs_net
@pytest.mark.parametrize("arm", ["real", "shuffled_class"])
def test_pruned_e1_and_e2a_episodes_are_bit_identical_frame_by_frame(arm):
    sh = None if arm == "real" else 1
    for run in (lambda pr: e1.run_e1_episode(9601, sh, max_frames=45, arm=arm, record_rows=True, pruned=pr),
                lambda pr: e2a.run_e2a_episode(9601, arm, sh, max_frames=45, record_rows=True, pruned=pr)):
        full, pruned = run(False), run(True)
        assert _hash(full[0], full[1]) == _hash(pruned[0], pruned[1])
