"""Part 7e: continue-from seeding, HOLDOUT-once guards, warm_7d start == 7d best."""
import json
import pickle
from pathlib import Path

import pytest

from flyrun import final7e, part7, search7

CFG = Path(__file__).resolve().parent.parent / "configs" / "part7.yaml"


def test_warm_7d_is_the_7d_best():
    cfg = part7.load_config(CFG)
    r = next(r for r in cfg["restarts"] if r["label"] == "warm_7d")
    best = json.loads((search7.ROOT / "evo7d" / "warm_r3" / "best_genome.json").read_text(encoding="utf-8"))
    assert r["u"] == best["u"]
    assert part7.decode(cfg, r["u"])[1] == best["genome"]


def test_continue_from_copies_and_reopens(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for f in ("gen.csv", "all_evals.csv", "best_genome.json"):
        (src / f).write_text("x")
    (src / "state.pkl").write_bytes(pickle.dumps(dict(gen=10, es=None, best=None, no_improve=7, done=True, secs=100.0)))
    d = tmp_path / "dst"
    search7._seed_continue(None, "r", d, src)
    st = pickle.loads((d / "state.pkl").read_bytes())
    assert (st["gen"], st["gen0"], st["done"], st["no_improve"], st["secs0"]) == (10, 10, False, 0, 100.0)


def test_holdout_refuses_uncommitted_final(monkeypatch):
    cfg = part7.load_config(CFG)
    monkeypatch.setattr(part7, "git_status", lambda paths: [])
    monkeypatch.setattr(part7, "_git", lambda *a: "")           # not in `git ls-files`
    with pytest.raises(SystemExit, match="not committed"):
        final7e.holdout(cfg, CFG, 1)


def test_holdout_refuses_second_run(monkeypatch, tmp_path):
    cfg = part7.load_config(CFG)
    monkeypatch.setattr(part7, "git_status", lambda paths: [])
    monkeypatch.setattr(part7, "_git", lambda *a: "ok" if a[0] == "ls-files" else "")
    lock = tmp_path / "lock"
    lock.write_text("x")
    monkeypatch.setattr(final7e, "LOCK", lock)
    with pytest.raises(SystemExit, match="already run"):
        final7e.holdout(cfg, CFG, 1)
