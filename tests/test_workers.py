# What this file does, in plain English:
# Checks that running evaluation episodes in worker processes that share one
# copy of the network in memory gives exactly the same answers, bit for bit, as
# running them one after another in a single process: for the real connectome
# and both shuffled controls. It also checks the shared copy holds the same
# numbers as the ordinary one.
"""brain/workers.py -- docs/SPEC_redesign_phase6c_part2.md. Needs the cached network and calibration."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from brain import builder, e1, workers
from brain.calibration import CALIBRATION_FILE

pytestmark = pytest.mark.skipif(not builder.default_path().exists() or not CALIBRATION_FILE.exists(),
                                reason="unified network / calibration not built")


def _rows_hash(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=repr).encode()).hexdigest()


def test_shared_arrays_equal_the_originals_and_variants_match_a_fresh_shuffle():
    net = builder.load_or_build()
    nset = workers.SharedNetworkSet(net, [(3, "degree"), (4, "class")])
    try:
        prov = workers._SharedProvider(nset.desc)
        real = prov.real()
        assert real.build_hash() == net.build_hash()
        for a in ("data", "indices", "indptr"):
            assert np.array_equal(getattr(real.W, a), getattr(net.W, a))
        assert not real.W.data.flags.owndata            # a view over the shared bytes, not a copy
        for seed, mode in ((3, "degree"), (4, "class")):
            mine, fresh = prov.variant(real, seed, mode), net.shuffled(seed, mode)
            assert mine.build_hash() == fresh.build_hash() and mine.twin_of == fresh.twin_of
            assert np.array_equal(mine.W.data, fresh.W.data) and np.array_equal(mine.W.indices, fresh.W.indices)
        assert prov.variant(real, 99, "degree") is None  # not shared: caller falls back to a private shuffle
    finally:
        nset.close()


def test_episode_telemetry_identical_through_the_shared_provider():
    net = builder.load_or_build()
    nset = workers.SharedNetworkSet(net, [(2, "degree")])
    plain = {a: _rows_hash(e1.run_e1_episode(9500, shuffle_seed=s, max_frames=30, record_rows=True, arm=a)[1])
             for a, s in (("real", None), ("shuffled", 2))}
    try:
        builder.install_shared(workers._SharedProvider(nset.desc))
        shared = {a: _rows_hash(e1.run_e1_episode(9500, shuffle_seed=s, max_frames=30, record_rows=True, arm=a)[1])
                  for a, s in (("real", None), ("shuffled", 2))}
    finally:
        builder.install_shared(None)
        nset.close()
    assert plain == shared


def test_parallel_workers_bit_identical_to_serial_for_three_arms():
    arms = ("real", "shuffled", "shuffled_class")
    serial = e1.run_eval(n=4, seed0=9500, workers=1, max_frames=40, arms=arms)
    parallel = e1.run_eval(n=4, seed0=9500, workers=2, max_frames=40, arms=arms)
    assert len(serial["episodes"]) == 12
    assert serial["episodes"] == parallel["episodes"]
    assert builder._SHARED is None                      # the parent never installs the provider
