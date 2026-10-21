"""NOTE: needs the old code to run: check out git tag `pre-cleanup` (it imports the removed `old_pkg` package).
Freeze the OLD code's answers into tests/data/golden/, so fly_mario can be tested with the old code gone.

Runs the old side of the four parity tests (tests/parity/*) exactly once and writes small versioned fixtures:

  brains.json        W sha256, neuron order (body ids), type/sign hashes, group-mask hashes of the 636/656/881/907 brains
  brains_rate.npz    the 907-neuron rate vector after 200 steps of the old update (the new update must reproduce it)
  mario.json.gz      per frame of three recorded button sequences: the old finders' enemies/walls/pits/? blocks/mushroom
  ceiling.json.gz    per frame of two sequences: the old headroom rise at 8 (feet, box height, span) probes
  runner.json.gz     the E1s champion's 10 HOLDOUT episodes: x + buttons per frame, outcome, max_x, score; the 8 genome values

Needs the old repo (the `old_pkg` package) and its tutorials/_cache. It is a one-off record of HOW the fixtures were
made; once the old code is deleted it can no longer run, and it does not have to (the fixtures are the record).

    python tools/freeze_golden.py all [--old-root DIR] [--cache DIR]      # or: brains | mario | ceiling | runner
Needs $FLY_MARIO_DATA (the new brains are read to drive the sequences, not to produce any answer).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
OUT = HERE.parents[1] / "tests" / "data" / "golden"
SRC = HERE.parents[1] / "src"


def sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def write_json_gz(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(OUT / name, "wb", mtime=0) as f:             # mtime=0: the same bytes every time
        f.write(json.dumps(obj, separators=(",", ":")).encode())
    print(f"wrote {name}: {(OUT / name).stat().st_size:,} bytes")


def rle(items) -> list:
    out = []
    for it in items:
        if out and out[-1][0] == it:
            out[-1][1] += 1
        else:
            out.append([it, 1])
    return out


def btn(b) -> str:
    return "+".join(b)                                              # () -> "" (no buttons)


# ---- brains ---------------------------------------------------------------------------------------------------
ROWS = [  # (mechanisms, old W file, old body table, neuron count)
    ((), "W_steer.npy", "steer_bodies.parquet", 636),
    (("hearing",), "W_steer_jo.npy", "steer_jo_bodies.parquet", 656),
    (("hearing", "attraction"), "W_steer_jo_orn.npy", "steer_jo_orn_bodies.parquet", 881),
    (("hearing", "attraction", "aversion"), "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet", 907),
]
SOUR = ("hearing", "attraction", "aversion")


def freeze_brains(cache: Path) -> None:
    import pandas as pd
    from fly_mario.fly.brain import RateModel, build_brain
    from fly_mario.fly.spec import BrainSpec
    from old_pkg import brain as OB                                  # the old loader, for masks and the update step

    rows = {}
    for mechs, wfile, bfile, n in ROWS:
        W, b = np.load(cache / wfile), pd.read_parquet(cache / bfile)
        assert W.shape == (n, n)
        rows[str(n)] = dict(mechanisms=list(mechs), n=n, W_sha256=sha(W.astype(np.float64)), body_ids=b.bodyId.astype(int).tolist(),
                            types_sha256=sha(b.type.to_numpy().astype("U40")), signs_sha256=sha(b.sign.to_numpy(float)))
    os.environ["OLD_WFILE"], os.environ["OLD_BODIES"] = "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet"
    try:
        masks = OB.load_brain(cache).masks
    finally:
        del os.environ["OLD_WFILE"], os.environ["OLD_BODIES"]
    rows["907"]["masks"] = {name: dict(count=int(m.sum()), sha256=sha(np.flatnonzero(m).astype(np.int64))) for name, m in sorted(masks.items())}

    # 200 steps of the old rate update; the sensor noise comes from the NEW brain's masks (same seed, same order as the old test)
    new = build_brain(BrainSpec(mechanisms=SOUR))
    W_old, model, rng = np.load(cache / "W_steer_jo_orn_sour.npy"), RateModel(), np.random.default_rng(123)
    h = np.zeros(new.n)
    for frame in range(20):
        I = np.zeros(new.n)
        for name, level in (("LPLC2_R", 0.4 + 0.02 * frame), ("LC4_R", 0.1), ("LC10a_R", 0.5)):
            m = new.masks[name]
            I[m] = level * (1.0 + 0.05 * rng.standard_normal(m.sum()))
        for _ in range(model.substeps):
            h = OB.step(h, W_old, model.g, I, model.alpha, model.clip)
    assert h.max() > 0
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "brains_rate.npz", h=h)
    (OUT / "brains.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"wrote brains.json ({(OUT / 'brains.json').stat().st_size:,} bytes), brains_rate.npz ({(OUT / 'brains_rate.npz').stat().st_size:,} bytes)")


# ---- mario: object boxes per frame ----------------------------------------------------------------------------
def old_view(ram, OE, OL, OS) -> dict:
    enemies = [(s, int(ram[OE.ADDR_ENEMY_TYPE + s]), int(ram[OS.ADDR_ENEMY_STATE + s]),
                int(ram[OE.ADDR_ENEMY_PAGE + s]) * 256 + int(ram[OE.ADDR_ENEMY_X + s]), int(ram[OS.ADDR_ENEMY_Y + s]))
               for s in range(OE.N_ENEMY_SLOTS) if int(ram[OE.ADDR_ENEMY_ACTIVE + s])]
    walls, pits = OL.scan_visible(ram, rim=True)
    threats = OS.enemy_boxes(enemies, walls)
    mush = OS.mushroom(ram)
    return dict(
        enemies=sorted([t.kind, int(t.ident[1]), int(t.x), int(t.top), int(t.w), int(t.h)] for t in threats),
        walls=sorted([int(x), int(h)] for x, h in dict(walls).items()),
        pits=sorted([int(a), int(b)] for a, b in pits),
        qblocks=sorted([int(a), int(b)] for a, b in OL.scan_blocks(ram)),
        mushroom=None if mush is None else [int(v) for v in mush],
    )


def old_modules(level):
    os.environ["OLD_LEVEL"] = level
    from old_pkg import env as OE, level as OL, senses_v2 as OS
    return OE, OL, OS


def driver_sequence(level, MarioEnv):
    from old_pkg import scripted
    drv, env = scripted.Driver(), MarioEnv()
    env.reset(level)
    seq = []
    for _ in range(2200):
        b = ("right", "A") if drv.act(env.ram) == 2 else ("right",)
        seq.append(b)
        if env.step(b).done:
            break
    return seq


def freeze_mario() -> None:
    from fly_mario.mario import ram as R
    from fly_mario.mario.env import MarioEnv
    cases = {}
    for level, kind in [("1-1", "driver"), ("1-2", "pulse"), ("1-1", "mushroom")]:
        OE, OL, OS = old_modules(level)
        env = MarioEnv()
        env.reset(level)
        facts = env.facts
        seq = driver_sequence(level, MarioEnv) if kind == "driver" else (
            [("right", "A") if i % 30 < 16 else ("right",) for i in range(2500)] if kind == "pulse" else None)
        used, views, hit, i = [], [], None, 0
        while True:
            if seq is not None:
                if i >= len(seq):
                    break
                b = seq[i]
            else:                                                   # mushroom: walk to a ? block, hit it from below, idle
                R.sweep_enemies(env, facts)
                if hit is None and R.mario_x(env.ram, facts) >= 318:
                    hit = 0
                b = ("right",) if hit is None else (("right", "A") if hit < 14 else ())
                if hit is not None:
                    hit += 1
                    if hit > 80:
                        break
            out = env.step(b)
            i += 1
            used.append(btn(b))
            views.append(old_view(env.ram, OE, OL, OS))
            if out.done:
                break
        cases[f"{level}/{kind}"] = dict(level=level, sweep=seq is None, frames=len(used), buttons=rle(used), views=rle(views))
        print(f"mario {level}/{kind}: {len(used)} frames, {len(cases[f'{level}/{kind}']['views'])} runs of identical views")
    write_json_gz("mario.json.gz", cases)


# ---- ceiling: headroom per frame ------------------------------------------------------------------------------
def freeze_ceiling() -> None:
    from fly_mario.mario import ram as R
    from fly_mario.mario.env import MarioEnv
    cases = {}
    for level, stop_x in [("1-2", 900), ("1-1", 1700)]:
        os.environ["OLD_LEVEL"] = level
        from old_pkg import level as OL, scripted
        from old_pkg.knobs import MAX_JUMP_HEIGHT
        env = MarioEnv()
        env.reset(level)
        f = env.facts
        drv = scripted.Driver()
        used, rises = [], []
        for i in range(4000):
            b = (("right", "A") if drv.act(env.ram) == 2 else ("right",)) if level == "1-1" else (("right", "A") if i % 30 < 16 else ("right",))
            out = env.step(b)
            used.append(btn(b))
            if out.done:
                break
            mx = R.mario_x(env.ram, f)
            left = int(env.ram[f["ram"]["screen_page"]]) * 256 + int(env.ram[f["ram"]["screen_x"]])
            right = left + f["grid"]["screen_w"]
            feet_now = int(env.ram[f["ram"]["mario_feet_y"]])
            row = []
            for feet in (176, feet_now):
                for box_h in (16, 24):
                    for x0, x1 in ((mx, mx + 12), (mx, min(mx + 160, right))):
                        row.append(int(OL.headroom(env.ram, x0, x1, feet, box_h)[1]))
            rises.append(row)
            if mx >= stop_x:
                break
        cases[level] = dict(level=level, stop_x=stop_x, max_jump_height=int(MAX_JUMP_HEIGHT), final_x=int(mx), buttons=rle(used),
                            rises=rle(rises), n_checked=len(rises))
        print(f"ceiling {level}: {len(used)} frames, {len(rises)} checked, final x {mx}")
    write_json_gz("ceiling.json.gz", cases)


# ---- runner: the champion's holdout episodes ------------------------------------------------------------------
HOLDOUT = [dict(noop=n, seed=100 + i + 1, sigma=sg) for sg in (0.0, 0.05) for i, n in enumerate((3, 11, 25, 33, 41))]


def freeze_runner(cache: Path, old_root: Path) -> None:
    os.environ["OLD_WFILE"], os.environ["OLD_BODIES"] = "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet"
    try:
        from old_pkg import e1s_genome as G
        from old_pkg.brain import load_brain
        from old_pkg.run import run_episode
        brain = load_brain(cache)
    finally:
        del os.environ["OLD_WFILE"], os.environ["OLD_BODIES"]
    values = json.load(open(old_root / "old_pkg" / "runs" / "E1s_progress.json"))["best"]["values"]
    knobs, enemy_input = G.knobs_for(values)
    episodes = []
    for ep in HOLDOUT:
        summary, df = run_episode(replace(knobs, SENSOR_NOISE=ep["sigma"]), brain, noop_start=ep["noop"], episode_seed=ep["seed"],
                                  stuck_frames=150, enemy_input=enemy_input)
        rows = df.iloc[ep["noop"]:].reset_index(drop=True)          # the noop frames are not the fly's
        episodes.append(dict(**ep, outcome=str(summary["end_reason"]), max_x=int(summary["max_x"]), score=int(summary["score"]),
                             n=len(rows), x=[int(v) for v in rows.x], buttons=rle(rows.buttons.tolist())))
        print(f"runner noop{ep['noop']} sigma{ep['sigma']}: {episodes[-1]['outcome']} max_x {episodes[-1]['max_x']} {len(rows)} frames")
    keys = ["HOME_R", "HUM_GAIN", "SMELL_GAIN", "SOUR_GAIN", "TTMN_THRESH", "RELEASE_THRESH", "STEER_THRESH", "MDN_THRESH"]
    write_json_gz("runner.json.gz", dict(episodes=episodes, e1s_values={k: float(values[k]) for k in keys}))


def find_old_root(arg) -> Path:
    for c in ([Path(arg)] if arg else []) + list(HERE.parents):
        if (c / "old_pkg" / "__init__.py").exists():
            return c
    sys.exit("old repo (a folder holding old_pkg/) not found: pass --old-root")


def find_cache(arg, old_root: Path) -> Path:
    env = os.environ.get("FLY_MARIO_OLD_CACHE")
    for c in ([Path(arg)] if arg else []) + ([Path(env)] if env else []) + [p / "tutorials" / "_cache" for p in [old_root, *HERE.parents]]:
        if (c / "W_steer.npy").exists():
            return c
    sys.exit("old tutorials/_cache not found: pass --cache or set FLY_MARIO_OLD_CACHE")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["all", "brains", "mario", "ceiling", "runner"])
    ap.add_argument("--old-root")
    ap.add_argument("--cache")
    a = ap.parse_args()
    old_root = find_old_root(a.old_root)
    cache = find_cache(a.cache, old_root)
    sys.path.insert(0, str(old_root))
    sys.path.insert(0, str(SRC))
    if a.what in ("all", "brains"):
        freeze_brains(cache)
    if a.what in ("all", "mario"):
        freeze_mario()
    if a.what in ("all", "ceiling"):
        freeze_ceiling()
    if a.what in ("all", "runner"):
        freeze_runner(cache, old_root)


if __name__ == "__main__":
    main()
