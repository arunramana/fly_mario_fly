# What this file does, in plain English:
# Checks the two control rewirings used to ask which wiring carries the jump advantage ("path_kept": real wiring inside the
# escape pathway, class-shuffled outside; "path_shuffled": the reverse). Counts per edge subset are preserved, the right
# edges are untouched, signs and degrees match the class shuffle, every seed gives a different rewiring, worker pools
# reproduce the serial run bit for bit, and the arms cannot be reached from the tool.
"""docs/SPEC_e1_features.md. Needs the cached network."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from brain import builder, e1, workers
from brain.calibration import CALIBRATION_FILE

pytestmark = pytest.mark.skipif(not builder.default_path().exists(), reason="unified network not built")
needs_cal = pytest.mark.skipif(not CALIBRATION_FILE.exists(), reason="calibration not built")


@pytest.fixture(scope="module")
def net():
    return builder.load_or_build()


def test_pathway_set_counts_and_definition(net):
    P = net.path_set()
    assert [len(net.pops[k]) for k in ("LC4", "LPLC2", "GF", "TTMn")] == [126, 185, 2, 2]
    assert P[np.concatenate([net.pops[k] for k in ("LC4", "LPLC2", "GF", "TTMn")])].all()
    A = (net.W != 0).tocsr()
    src = np.concatenate([net.pops["LC4"], net.pops["LPLC2"]])
    tgt = np.concatenate([net.pops["GF"], net.pops["TTMn"]])
    for x in np.flatnonzero(P)[:60]:                       # every member is a core neuron or a one-intermediate relay
        core = x in src or x in tgt
        assert core or ((A[x, src] != 0).nnz > 0 and (A[tgt, x] != 0).nnz > 0)
    assert int(P.sum()) == 442 and int(net.path_edge_mask().sum()) == 13291


@pytest.mark.parametrize("mode", builder.PATH_MODES)
def test_mode_invariants_on_a_few_seeds(net, mode):
    among = net.path_edge_mask()
    P = net.path_set()
    group = net.tier_groups()
    cls = net.shuffled(1, "class")
    assert np.array_equal(cls.post, builder.BuiltNetwork._class_permuted_post(net, 1, np.ones(len(net.post), bool)))
    for seed in (1, 2, 3):
        t = net.shuffled(seed, mode)
        moved_subset = ~among if mode == "path_kept" else among
        # nothing outside the shuffled subset changes; pre, syn, signs and ids are shared with the real network
        assert np.array_equal(t.post[~moved_subset], net.post[~moved_subset])
        assert np.array_equal(t.pre, net.pre) and np.array_equal(t.syn, net.syn) and np.array_equal(t.signs, net.signs)
        # inside the subset: a permutation of the post column within each tier group (counts per subset and group preserved)
        for g in np.unique(group[net.post[moved_subset]]):
            rows = moved_subset & (group[net.post] == g)
            assert np.array_equal(np.sort(t.post[rows]), np.sort(net.post[rows]))
            assert (group[t.post[rows]] == g).all()
        # in-degree, out-degree and per-subset edge counts as in the class shuffle
        n = net.n_neurons
        assert np.array_equal(np.bincount(t.pre, minlength=n), np.bincount(net.pre, minlength=n))
        assert int((t.post[moved_subset] >= 0).sum()) == int(moved_subset.sum())
        if mode == "path_shuffled":
            assert int((P[t.pre] & P[t.post]).sum()) == int(among.sum())          # exactly the edges among P, rewired inside P
            assert np.array_equal(np.sort(t.post[among]), np.sort(net.post[among]))
        else:
            assert np.array_equal(t.post[among], net.post[among])                  # edges among P identical to real
            assert int((P[t.pre] & P[t.post]).sum()) >= int(among.sum())           # plus a few by chance (SPEC section 3)
        assert t.twin_of == {"seed": seed, "real_hash": net.build_hash(), "mode": mode}
        assert t.build_hash() != net.build_hash() and t.build_hash() != cls.build_hash()


@pytest.mark.parametrize("mode", builder.PATH_MODES)
def test_fifty_distinct_rewirings_over_seeds_1_to_50(net, mode):
    hashes = {net.shuffled(s, mode).build_hash() for s in range(1, 51)}
    assert len(hashes) == 50


def test_unknown_mode_refused_and_class_mode_unchanged(net):
    with pytest.raises(ValueError):
        net.shuffled(1, "path_everything")
    # the class mode keeps its pre-refactor bits: reference implementation inline (the old loop)
    post = net.post.copy()
    rng = np.random.default_rng(7)
    group = net.tier_groups()[net.post]
    for g in np.unique(group):
        rows = np.flatnonzero(group == g)
        post[rows] = net.post[rows[rng.permutation(len(rows))]]
    assert np.array_equal(net.shuffled(7, "class").post, post)


def test_arms_registered_and_tool_cannot_reach_them():
    assert {"path_kept", "path_shuffled"} <= set(e1.ARM_CHOICES) and not {"path_kept", "path_shuffled"} & set(e1.ARMS)
    assert e1.ARM_SHUFFLE_MODE["path_kept"] == "path_kept" and "path_kept" in e1.SHUFFLED_ARMS
    root = Path(__file__).resolve().parent.parent
    users = {p.relative_to(root).as_posix() for p in (root / "brain").glob("*.py")
             if re.search(r"path_kept|path_shuffled", p.read_text(encoding="utf-8"))}
    assert users == {"brain/builder.py", "brain/e1.py"}, users
    tool_users = [p for p in (root / "tool").rglob("*.py") if re.search(r"path_kept|path_shuffled", p.read_text(encoding="utf-8"))
                  and "tests" not in p.parts]
    assert not tool_users
    import inspect
    from tool.core import brain_runner
    assert "path_" not in inspect.getsource(brain_runner)


def test_shared_variants_match_fresh_shuffles(net):
    nset = workers.SharedNetworkSet(net, [(5, "path_kept"), (5, "path_shuffled")])
    try:
        prov = workers._SharedProvider(nset.desc)
        real = prov.real()
        for mode in builder.PATH_MODES:
            mine, fresh = prov.variant(real, 5, mode), net.shuffled(5, mode)
            assert mine.build_hash() == fresh.build_hash() and mine.twin_of == fresh.twin_of
            assert np.array_equal(mine.W.data, fresh.W.data) and np.array_equal(mine.W.indices, fresh.W.indices)
    finally:
        nset.close()


def test_hundred_variants_fit_under_the_shared_cap(net):
    per_mb = sum(v.nbytes for v in (net.post, net.insub, net.W.data, net.W.indices, net.W.indptr)) / 2**20
    assert 100 * per_mb <= workers.MAX_SHARED_VARIANT_MB       # both new arms at n = 50 share; with class too the tail is private


@needs_cal
def test_parallel_workers_bit_identical_to_serial_for_the_path_arms():
    arms = ("path_kept", "path_shuffled")
    serial = e1.run_eval(n=3, seed0=9500, workers=1, max_frames=40, arms=arms)
    parallel = e1.run_eval(n=3, seed0=9500, workers=2, max_frames=40, arms=arms)
    assert len(serial["episodes"]) == 6 and serial["episodes"] == parallel["episodes"]
    assert builder._SHARED is None
