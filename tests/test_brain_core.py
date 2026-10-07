# What this file does, in plain English:
# Tests the redesigned brain core: the manifest counts, the network builder (on small
# toy graphs and on the saved real network), that stimuli can only enter at
# sensory-tier neurons, that nothing else can add current to a neuron, that the
# motor map only reads, that results carry their stamp, and the looming disc and
# resting-state behaviour of the real wiring against a shuffled twin.
"""docs/SPEC_brain_core.md section 8. Toy-graph tests need no data; the real-network tests use the cached network
(`../data/derived/brain_k3_N5.npz`) and skip with a reason when it has not been built."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

import brain
from brain import builder
from brain.brain import Brain, Readout, StimulusError
from brain.calibration import CALIBRATION_FILE, Calibration, MotorThresholds
from brain.manifest import MOTOR_TABLE, UNASSIGNED_BUTTONS, Manifest, Population, Segment, Select, SENSORY, OUTPUT
from brain.mechanisms import LoomingMechanism, Stimulus
from brain.motor_map import MotorMap
from fly.connectome import circuit

BRAIN_DIR = Path(brain.__file__).parent
needs_net = pytest.mark.skipif(not builder.default_path().exists(), reason="unified network not built (python -m brain.builder)")
needs_cal = pytest.mark.skipif(not CALIBRATION_FILE.exists(), reason="brain/calibration.json missing (python -m brain.calibrate)")


# ---- builder on toy graphs -------------------------------------------------------------------------------------
def _toy_edges():
    # 0=S, 1=a, 2=T, 3=b, 4=c, 5=d, 6=e   edges: S->a->T (2 hops), S->b->c->T (3), d->T (not from S), S->e (dead end)
    pre = np.array([0, 1, 0, 3, 4, 5, 0])
    post = np.array([1, 2, 3, 4, 2, 2, 6])
    return builder.EdgeTable(ids=np.arange(10, 17), pre=pre, post=post, w=np.full(7, 6), total_in=np.full(7, 20.0))


def test_path_union_keeps_exactly_the_on_path_neurons():
    pops = {"S": np.array([10]), "T": np.array([12])}
    m = Manifest(populations=(Population("S", SENSORY, Select()), Population("T", OUTPUT, Select())),
                 segments=(Segment("s", ("S",), ("T",)),), whole=(), k=2)
    assert list(builder.path_union(_toy_edges(), pops, m)) == [0, 1, 2]
    assert list(builder.path_union(_toy_edges(), pops, Manifest(populations=m.populations, segments=m.segments, whole=(), k=3))) == [0, 1, 2, 3, 4]
    m_whole = Manifest(populations=m.populations, segments=m.segments, whole=("T", "S"), k=1)
    assert set(builder.path_union(_toy_edges(), pops, m_whole)) == {0, 2}     # nothing within 1 hop, whole populations only


def test_sparse_weight_matrix_equals_the_circuit_recipe():
    rng = np.random.default_rng(0)
    n = 40
    pre, post = rng.integers(0, n, 300), rng.integers(0, n, 300)
    keep = pre != post
    pairs = pd.DataFrame({"body_pre": pre[keep], "body_post": post[keep]}).drop_duplicates()
    pairs["weight"] = rng.integers(5, 30, len(pairs))
    signs = rng.choice([-1.0, 1.0, 0.0], n)
    W, _ = builder.weight_matrix(n, pairs["body_pre"].to_numpy(), pairs["body_post"].to_numpy(), pairs["weight"].to_numpy(), signs)
    bodies = pd.DataFrame({"bodyId": np.arange(n), "type": "x", "somaSide": "L"})
    edges = pairs.assign(n_edges=1)
    W_ref, _, _ = circuit.build_weight_matrix(bodies, edges, pd.Series(np.full(n, 1e3), index=np.arange(n)),
                                              pd.Series(signs, index=np.arange(n)))
    assert np.allclose(W.toarray(), W_ref)


def _toy_network() -> builder.BuiltNetwork:
    rng = np.random.default_rng(1)
    n = 60
    pre, post = rng.integers(0, n, 400), rng.integers(0, n, 400)
    return builder.BuiltNetwork(ids=np.arange(n) + 1000, side=np.array(["L", "R"] * 30), signs=rng.choice([-1.0, 1.0], n),
                                pops={}, pre=pre, post=post, syn=rng.integers(5, 30, 400), total_in=np.zeros(n), rule={"k": 3})


def test_shuffle_preserves_degrees_signs_and_neurons():
    net = _toy_network()
    twin = net.shuffled(seed=3)
    assert (twin.ids == net.ids).all() and (twin.signs == net.signs).all()
    assert (np.bincount(twin.pre, minlength=60) == np.bincount(net.pre, minlength=60)).all()      # out-degree
    assert (np.bincount(twin.post, minlength=60) == np.bincount(net.post, minlength=60)).all()    # in-degree
    assert not (twin.post == net.post).all()
    assert twin.twin_of["real_hash"] == net.build_hash() and net.twin_of is None


def test_weight_rows_are_normalised_by_in_network_input():
    net = _toy_network()
    for j in range(60):
        row = net.W.getrow(j)
        col_signs = net.signs[row.indices]
        assert np.isclose(np.abs(row.data).sum(), (net.syn[net.post == j][net.signs[net.pre[net.post == j]] != 0]).sum()
                          / net.syn[net.post == j].sum()) or net.syn[net.post == j].sum() == 0
        assert (np.sign(row.data) == col_signs).all()


# ---- manifest ----------------------------------------------------------------------------------------------------
def test_motor_table_leaves_down_and_up_unassigned_and_names_only_outputs():
    mf = Manifest()
    outputs = set(mf.names(OUTPUT))
    assert set(UNASSIGNED_BUTTONS) == {"down", "up"}
    assert {r.button for r in MOTOR_TABLE} == {"A", "walk", "left", "right", "back"}
    for r in MOTOR_TABLE:
        assert set(r.populations) <= outputs


def test_manifest_resolves_to_the_verified_counts():
    pytest.importorskip("mcns", reason="needs ../mcns.py")
    import mcns
    if not mcns.ANNOTATIONS.exists():
        pytest.skip("MaleCNS annotations not available")
    ann = mcns.load_annotations(["bodyId", "type", "class", "superclass"])
    pops = Manifest().resolve(ann)
    assert len(pops["LC4"]) + len(pops["LPLC2"]) == 311 and len(pops["GF"]) == 2 and len(pops["MDN"]) == 4
    assert len(pops["KC"]) == 4064 and len(pops["ORN"]) == 2639


# ---- the real saved network ------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def net():
    return builder.BuiltNetwork.load(builder.default_path())


def _stub(net, **kw):
    mt = MotorThresholds(0.9, 1.0, 1.0, 1.0, 1.0)
    return Calibration(net.build_hash(), 1.0, 0.85, 0.25, mt, **kw)


@needs_net
def test_saved_network_carries_its_rule_counts_and_both_sides(net):
    r = net.rule
    assert r["k_hops"] == 3 and r["min_synapses"] == 5 and r["counts"]["neurons"] == net.n_neurons == len(net.ids)
    assert r["counts"]["edges"] == net.n_edges
    assert set(r["whole_populations"]) == {"KC", "MBON", "DAN"}
    for pop in ("LC4", "LPLC2"):
        idx = net.pops[pop]
        assert set(net.side[idx]) == {"L", "R"}
    assert len(net.pops["KC"]) == 4064 and len(net.pops["GF"]) == 2


@needs_net
def test_stimulus_api_accepts_only_sensory_tier_ids(net):
    b = Brain(net, _stub(net))
    gf_id, kc_id = net.ids[net.pops["GF"][0]], net.ids[net.pops["KC"][0]]
    with pytest.raises(StimulusError):
        b.stimulate([gf_id], [1.0])
    with pytest.raises(StimulusError):                                    # a mix is refused whole: nothing is added
        b.stimulate([net.ids[net.pops["LC4"][0]], kc_id], [1.0, 1.0])
    assert not b._current.any()
    orn = net.ids[net.pops["ORN"][:5]]
    b.stimulate(orn, 2.0)
    assert set(np.flatnonzero(b._current)) == set(net.local(orn)) and (b._current[net.local(orn)] == 2.0).all()
    b.step_frame()
    assert not b._current.any()                                            # a stimulus lasts one frame


@needs_net
def test_the_sensory_tier_is_exactly_the_manifest_sensory_populations(net):
    b = Brain(net, _stub(net))
    expected = np.sort(np.concatenate([net.ids[net.pops[n]] for n in Manifest().names(SENSORY)]))
    assert (b.sensory_ids == expected).all()
    assert not np.isin(b.sensory_ids, net.ids[net.pops["GF"]]).any() and not np.isin(b.sensory_ids, net.ids[net.pops["KC"]]).any()


def test_no_other_path_adds_current():
    public = {n for n, _ in inspect.getmembers(Brain, callable) if not n.startswith("_")}
    assert public == {"attach", "apply", "stimulate", "reset", "step_frame", "stamp", "population_rate"}      # + sensory_ids; population_rate only reads
    writes = []
    for f in BRAIN_DIR.glob("*.py"):
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if re.search(r"_current\b\s*(\[[^\]]*\])?\s*[+\-*]?=(?!=)|add\.at\(self\._current|\.h\[[^\]]*\]\s*[+\-*]?=(?!=)|\.h\s*\+=", code):
                writes.append(f"{f.name}:{ln}:{code.strip()}")
    # the control-only lesion REMOVES activity of an output population (a write of the 0 clamp, never a positive value)
    allowed = ("np.add.at(self._current", "self._current = np.zeros", "net.h[:] = 0.0",
               "self._net.h[self._lesion_idx] = LESION_CLAMP_HZ")
    assert all(any(a in w for a in allowed) for w in writes), writes
    assert sum("np.add.at(self._current" in w for w in writes) == 1


@needs_net
def test_calibration_for_another_network_is_refused(net):
    stub = _stub(net)
    bad = Calibration("deadbeef", stub.rho, stub.g, stub.gf_threshold, stub.motor)
    with pytest.raises(ValueError):
        Brain(net, bad)
    Brain(net.shuffled(1), stub)                                            # a twin of the calibrated network is fine


@needs_net
def test_looming_mechanism_drives_only_lc4_and_lplc2_with_the_right_values(net):
    mech = LoomingMechanism(net)
    s = mech.encode({"L": 0.5, "R": 0.25}, {"L": -0.01, "R": 0.02})
    assert isinstance(s, Stimulus) and len(s.body_ids) == 311
    lc4, lplc2 = set(net.ids[net.pops["LC4"]]), set(net.ids[net.pops["LPLC2"]])
    assert set(s.body_ids) == lc4 | lplc2
    side = dict(zip(net.ids, net.side))
    val = dict(zip(s.body_ids, s.values))
    for b in lc4:
        assert val[b] == pytest.approx(0.01 if side[b] == "L" else 0.02)
    for b in lplc2:
        assert val[b] == pytest.approx(0.0 if side[b] == "L" else 0.25)    # L is shrinking: gated off (Step 7); R expands


def _loom_vals(net, theta, dtheta):
    """(LPLC2 value, LC4 value) of the left hemisphere for one encode call."""
    s = LoomingMechanism(net).encode({"L": theta, "R": theta}, {"L": dtheta, "R": dtheta})
    side, val = dict(zip(net.ids, net.side)), dict(zip(s.body_ids, s.values))
    pick = lambda pop: {val[b] for b in net.ids[net.pops[pop]] if side[b] == "L"}
    (lplc2,), (lc4,) = pick("LPLC2"), pick("LC4")
    return lplc2, lc4


@needs_net
def test_expansion_gate_size_channel_needs_strictly_positive_dtheta(net):
    """Step 7: looming means expansion. theta reaches LPLC2 only while dtheta > 0; LC4 stays |dtheta| in every case."""
    assert _loom_vals(net, 0.5, 0.01) == pytest.approx((0.5, 0.01))        # expanding: passes
    assert _loom_vals(net, 3.0, 0.0) == (0.0, 0.0)                           # wall at touching distance (theta ~ 172 deg, dtheta 0): no size cue
    assert _loom_vals(net, 0.5, -0.02) == pytest.approx((0.0, 0.02))       # receding: no size cue, LC4 still fires (existing property)


@needs_net
def test_expansion_gate_first_frame_of_an_object_has_no_size_cue(net):
    """prev theta undefined (0): dtheta == theta, which is an appearance, not an observed expansion. LC4 still sees it."""
    assert _loom_vals(net, 0.4, 0.4) == pytest.approx((0.0, 0.4))
    assert _loom_vals(net, 0.5, 0.1) == pytest.approx((0.5, 0.1))          # second frame: prev 0.4 > 0


@needs_net
def test_obstacle_expansion_inherits_the_same_gate(net):
    from brain.mechanisms import ObstacleExpansion
    s = ObstacleExpansion(net).encode({"L": 3.0, "R": 3.0}, {"L": 0.0, "R": 0.0})
    assert not s.values.any()


@needs_net
def test_attach_rejects_a_mechanism_outside_the_sensory_tier(net):
    class Bad:
        name, populations, evidence = "bad", ("KC",), ""
    with pytest.raises(StimulusError):
        Brain(net, _stub(net)).attach(Bad())


# ---- motor map ---------------------------------------------------------------------------------------------------
def _readout(ttmn=0.0, dnp09=0.0, mdn=0.0, dna_l=0.0, dna_r=0.0):
    rates = {(p, s): 0.0 for p in ("GF", "TTMn", "DNp09", "DNa01", "DNa02", "MDN") for s in "LR"}
    for s in "LR":
        rates[("TTMn", s)], rates[("DNp09", s)], rates[("MDN", s)] = ttmn, dnp09, mdn
    for p in ("DNa01", "DNa02"):
        rates[(p, "L")], rates[(p, "R")] = dna_l, dna_r
    return Readout(rates, False, 0.0)


def test_motor_map_reads_buttons_and_never_presses_down_or_up():
    mm = MotorMap(MotorThresholds(0.9, 5.0, 0.5, 0.5, 0.5))
    assert not any(vars(mm.read(_readout())).values())
    held = [mm.read(_readout(ttmn=20.0)).a]                                   # onset presses A
    held += [mm.read(_readout(ttmn=20.0)).a for _ in range(40)]               # sustained level adds nothing: the drive decays
    assert held[0] and not held[-1]
    mm.reset()
    b = mm.read(_readout(dnp09=2.0))
    assert b.right and b.b and not b.left
    assert mm.read(_readout(mdn=2.0)).left
    assert mm.read(_readout(dna_l=3.0, dna_r=0.0)).left and mm.read(_readout(dna_l=0.0, dna_r=3.0)).right
    for r in (_readout(ttmn=30, dnp09=9, mdn=9, dna_l=9), _readout(dna_r=9)):
        b = mm.read(r)
        assert not b.down and not b.up


def test_motor_map_has_no_route_into_the_brain():
    sig = inspect.signature(MotorMap.__init__)
    assert list(sig.parameters) == ["self", "thresholds", "table"]
    src = (BRAIN_DIR / "motor_map.py").read_text(encoding="utf-8")
    assert "Brain(" not in src and "stimulate" not in src and "apply(" not in src


# ---- calibrated behaviour on the synthetic bench ----------------------------------------------------------------
@pytest.fixture(scope="module")
def calibrated(net):
    return Calibration.load()


@needs_net
@needs_cal
def test_calibration_file_matches_the_saved_network(net, calibrated):
    assert calibrated.network_hash == net.build_hash()
    assert calibrated.g <= 0.85 / calibrated.rho + 1e-9 and calibrated.g <= 1.0
    assert calibrated.motor.a_threshold > 0 and calibrated.gf_threshold > 0


@needs_net
@needs_cal
def test_rest_is_silent_and_gf_fires_near_40_deg_real_but_not_shuffled(net, calibrated):
    from brain.disc import first, rest_run, run_disc
    real = Brain(net, calibrated)
    rest = rest_run(real, 400, 0)
    assert not any(r.gf_spiked for r in rest)
    mm = MotorMap(calibrated.motor)
    assert not any(any(vars(mm.read(r)).values()) for r in rest[100:])
    rec = run_disc(real, LoomingMechanism(net), 40)
    f = first(rec, "spike")
    assert f is not None and 35.0 <= f["theta"] <= 50.0
    twin = Brain(net.shuffled(1), calibrated)
    g = first(run_disc(twin, LoomingMechanism(net), 40), "spike")
    assert g is None or g["theta"] > f["theta"]


@needs_net
@needs_cal
def test_policy_stamps_rule_hash_and_mechanisms(net, calibrated):
    from brain.policy import BrainPolicy
    p = BrainPolicy(network=net, calibration=calibrated)

    class Obs:
        ram = np.zeros(2048, dtype=np.uint8)
    p.reset(0)
    assert isinstance(p.act(Obs()), int)
    s = p.stamp()
    assert s["mechanisms"] == ["looming"] and s["build_rule"]["k_hops"] == 3 and s["shuffled"] is None
    assert s["calibration_hash"] == Calibration.file_hash() and s["build_hash"] == net.build_hash()
    t = BrainPolicy(network=net, calibration=calibrated, shuffle_seed=2).stamp()
    assert t["shuffled"]["seed"] == 2


# ---- elevation encoding (defect D1), synthetic ground-level object only -------------------------------------------
def _ground_scene(d: int, enemy_y_byte: int = 184, size: int = 0) -> np.ndarray:
    """RAM of small Mario standing on flat ground (player Y byte 176, feet y 208) and a Goomba d px ahead on the same
    floor (enemy Y byte 184: the engine's enemy baseline is 8 px off the player's). Offsets measured on 1-1."""
    ram = np.zeros(2048, dtype=np.uint8)
    ram[0x86], ram[0x6D], ram[0xCE], ram[0x4AF], ram[0x756] = 100, 0, 176, 208, size
    ram[0x0F], ram[0x16], ram[0x6E], ram[0x87], ram[0xCF] = 1, 6, 0, 100 + d, enemy_y_byte
    return ram


def test_same_level_object_has_zero_elevation_and_full_theta_at_several_distances():
    import math
    from bridge.perception import VisibleRegistry, bio_enemy_thetas
    from brain.calibration import ELEVATION_LIMIT_DEG
    from brain.perception import enemy_thetas
    from mario.entities.registry import DEFAULT
    from types import SimpleNamespace
    reg = VisibleRegistry(DEFAULT)
    for d in (22, 30, 45, 70, 120):
        ram = _ground_scene(d)
        theta, _, dist = enemy_thetas(ram, {"L": 0.0, "R": 0.0}, reg, ELEVATION_LIMIT_DEG)
        assert dist["R"] == d - 10                                                             # step 4: surface to surface (small Mario)
        assert theta["L"] == theta["R"] == pytest.approx(2 * math.atan(5 / (d - 10)), rel=1e-12)  # w = 10 hitbox, weight exactly 1
        old, _, _ = bio_enemy_thetas(ram, {"L": 0.0, "R": 0.0}, reg, SimpleNamespace(elevation_limit_deg=ELEVATION_LIMIT_DEG))
        if d <= 45:
            assert old["R"] < 2 * math.atan(8 / d) * 0.9  # the frozen raw-byte version (w = 16, centre d) reads this as an elevated object
    # the calibrated GF angle (40 deg) is reachable by an object on the floor, at d_centre = 23.7 px (surface 13.74; step 4)
    th, _, _ = enemy_thetas(_ground_scene(24), {"L": 0.0, "R": 0.0}, reg, ELEVATION_LIMIT_DEG)
    assert math.degrees(th["R"]) == pytest.approx(40.0, abs=1.5)
    assert math.degrees(2 * math.atan(5 / (5 / math.tan(math.radians(20))))) == pytest.approx(40.0)   # the frozen distance 13.74
    big, _, bdist = enemy_thetas(_ground_scene(30, size=1), {"L": 0.0, "R": 0.0}, reg, ELEVATION_LIMIT_DEG)
    assert bdist["R"] == 30 - 11                                                          # big Mario: front edge 14, so d_centre - 11
    # an object raised 16 px (not same level) is down-weighted, and one behind Mario contributes nothing
    up, _, _ = enemy_thetas(_ground_scene(24, enemy_y_byte=184 - 16), {"L": 0.0, "R": 0.0}, reg, ELEVATION_LIMIT_DEG)
    assert 0.0 < up["R"] < th["R"] * 0.5
    ram = _ground_scene(24)
    ram[0x87] = 60
    assert enemy_thetas(ram, {"L": 0.0, "R": 0.0}, reg, ELEVATION_LIMIT_DEG)[0]["R"] == 0.0


# ---- edge counts and unknown-transmitter neurons ------------------------------------------------------------------
@needs_net
def test_stamp_reports_both_edge_counts_and_where_the_unknown_transmitter_neurons_are(net):
    r = net.edge_report()
    assert r["built_edges"] == len(net.pre) and r["nonzero_weights"] == net.n_edges
    assert r["built_edges"] - r["nonzero_weights"] == r["edges_dropped_unknown_source"]
    assert r["unknown_transmitter_neurons"] == int((net.signs == 0).sum())
    by_pop = r["unknown_transmitter_by_population"]
    for pop in ("LC4", "LPLC2", "GF", "TTMn", "DNp09", "DNa01", "DNa02", "MDN"):      # no looming input or motor output
        assert pop not in by_pop
    assert Brain(net, _stub(net)).stamp()["built_edges"] == r["built_edges"]


# ---- thin rest margin: reported, never re-tuned -------------------------------------------------------------------
@needs_net
@needs_cal
def test_rest_margin_is_reported_for_real_and_shuffled(net, calibrated, record_property):
    from brain.disc import rest_margin
    real = rest_margin(Brain(net, calibrated), 800, 0)
    twin = rest_margin(Brain(net.shuffled(1), calibrated), 800, 0)
    for name, m in (("real", real), ("shuffled", twin)):
        for k, v in m.items():
            record_property(f"rest_margin_{name}_{k}", round(v["ratio"], 3))
            print(f"rest margin {name} {k}: max {v['max']:.4f} / threshold {v['threshold']:.4f} = {v['ratio']:.2f}")
    assert set(real) == {"walk", "steer", "back"}
    assert all(v["ratio"] < 1.0 for v in real.values())          # the real brain is silent at rest (thresholds untouched)


# ---- brain scalar registry ----------------------------------------------------------------------------------------
@needs_cal
def test_every_calibration_constant_is_registered_and_the_doc_is_generated_from_it():
    from brain import calibration as C
    from brain import scalars
    names = {s.name for s in scalars.all_scalars()}
    constants = {n for n, v in vars(C).items() if n.isupper() and isinstance(v, (int, float, tuple)) and n != "CALIBRATION_FILE"}
    for n in constants:
        assert n in names or any(x.startswith(n + "[") for x in names), f"{n} is not in brain/scalars.py"
    assert {s.kind for s in scalars.all_scalars()} <= set(scalars.KINDS)
    assert next(s for s in scalars.all_scalars() if s.name == "ELEVATION_LIMIT_DEG").kind == scalars.INVENTED
    assert next(s for s in scalars.all_scalars() if s.name == "CLIP_HZ").kind == scalars.INVENTED
    assert scalars.DOC_PATH.read_text(encoding="utf-8") == scalars.generate(), \
        "docs/SCALARS_BRAIN.md is out of date: run `.venv/Scripts/python.exe -m brain.scalars`"


# ---- evaluation wiring --------------------------------------------------------------------------------------------
def test_brain_eval_defaults_are_the_held_out_seeds_and_the_metric_summary_works():
    from brain import evaluation as ev
    assert ev.DEFAULT_SEED0 == 2000 and ev.DEFAULT_N == 20 and ev.LEVEL == "1-1"
    rs = [ev.EpisodeResult("real", 2000 + i, i < 3, False, False, 10, 100, 90, 0, 0) for i in range(4)]
    s = ev.summarize(rs)
    assert s["n"] == 4 and s["passed"] == 3 and 0.0 < s["pass_rate_ci"][0] < s["pass_rate"] < s["pass_rate_ci"][1] <= 1.0
