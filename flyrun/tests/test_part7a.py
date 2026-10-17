"""Part 7a: the pre-registration config validates, HOLDOUT is the Part 6b list, 7d/7e refuse a dirty tree,
and r3 replays to Part 6b's HOLDOUT number."""
import copy
from pathlib import Path

import pytest

from flyrun import episodes4, part7

CFG = Path(__file__).resolve().parent.parent / "configs" / "part7.yaml"


@pytest.fixture
def cfg():
    return part7.load_config(CFG)


def test_yaml_loads_and_validates(cfg):
    assert part7.validate(cfg) == []
    assert [k["name"] for k in cfg["knobs"]] == ["G", "TTMN_THRESH", "A_HOLD", "COOLDOWN", "HOME_R", "PIT_GAIN"]
    assert all(k["tag"].startswith("INVENTED") for k in cfg["knobs"])
    assert [r["label"] for r in cfg["restarts"]] == ["warm_r3", "fresh_97", "fresh_96", "fresh_95"]
    assert len(cfg["episodes"]["train"]) == 6 and len(cfg["episodes"]["holdout"]) == 10


def test_bad_range_fails(cfg):
    bad = copy.deepcopy(cfg)
    bad["knobs"][0]["lo"], bad["knobs"][0]["hi"] = 1.5, 0.2
    assert any("lo >= hi" in e for e in part7.validate(bad))


def test_missing_seed_fails(cfg):
    bad = copy.deepcopy(cfg)
    del bad["restarts"][0]["cma_seed"]
    assert any("cma_seed" in e for e in part7.validate(bad))
    bad = copy.deepcopy(cfg)
    del bad["episodes"]["train"][2]["seed"]
    assert any("episodes.train" in e for e in part7.validate(bad))


def test_too_many_new_knobs_fails(cfg):
    bad = copy.deepcopy(cfg)
    bad["conditional_knob_rule"]["with"].append(dict(name="X", lo=0, hi=1, tag="INVENTED (evolved)"))
    assert any("more than 2" in e for e in part7.validate(bad))


def test_holdout_equals_part6b(cfg):
    ho = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=float(e["sigma"])) for e in cfg["episodes"]["holdout"]]
    assert ho == [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]


def test_train_and_holdout_seeds_disjoint(cfg):
    assert not {e["seed"] for e in cfg["episodes"]["train"]} & {e["seed"] for e in cfg["episodes"]["holdout"]}


@pytest.mark.parametrize("stage", ["7d", "7e"])
def test_search_stages_refuse_dirty_tree(stage, monkeypatch):
    monkeypatch.setattr(part7, "git_status", lambda paths: [" M flyrun/knobs.py"])
    with pytest.raises(SystemExit, match="uncommitted"):
        part7.main(["--config", str(CFG), "--stage", stage])


def test_search_stages_are_stubs_on_clean_tree(monkeypatch):
    monkeypatch.setattr(part7, "git_status", lambda paths: [])
    with pytest.raises(NotImplementedError):
        part7.main(["--config", str(CFG), "--stage", "7d"])


def test_r3_replay_reproduces_part6b_holdout(cfg):
    import multiprocessing as mp
    r3 = next(r for r in cfg["restarts"] if r["label"] == "warm_r3")
    knobs, _ = part7.decode(cfg, r3["u"])
    with mp.get_context("spawn").Pool(5, initializer=part7._init) as pool:
        ev = part7.evaluate(pool, cfg, knobs, "holdout")
    assert round(ev["mean_max_x"], 1) == 1405.1 and ev["flags"] == 1
