# What this file does, in plain English:
# Trains the fly's mushroom body (its learning centre) by playing level 1-1
# over and over from the same start, carrying the learned weights from one
# episode to the next. Every episode -- the untrained baseline, each
# training episode, and the optional shuffled-wiring control networks -- is
# recorded through the tool's run store, so it shows up in the Player and
# the Learning chart. Video frames are kept only for a few episodes to save
# disk; telemetry is kept for all. Optionally each episode gets its own noise
# seed, and every N episodes the current weights are tested, frozen, on a
# held-out set of seeds; those results go to a small JSON file next to the
# checkpoints.
"""tool/core/training.py -- the one training path (Goal tab's Train button,
`scripts/train_mushroom_body.py`). Never write runs anywhere but
`tool.core.run_store`.

Frame-keeping policy (200 episodes with full frames is ~800 MB):
  baseline           always
  real network       every 10th episode, the best so far, the last
  shuffled networks  the best so far and the last
Telemetry is kept for every episode.
"""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path

import numpy as np

from config.output_routing import PROJECTS_ROOT, resolve_run_path
from tool.core.frame_store import FrameStore
from tool.core.savestates import load_state
from tool.core.run_store import (list_runs, next_run_number, patch_run, record_run,
                                 write_run_note)

EVAL_FILE = "training_eval.json"
GROUP_BASELINE = "Baseline"
GROUP_REAL = "Training · real"
EVERY_NTH = 10
WARMUP_FRAMES = 60


def group_for_shuffled(n: int) -> str:
    return f"Training · shuffled {n}"


class PaletteFrameStore(FrameStore):
    """FrameStore with a fast path: once the (small, ~50 colour) palette is
    known, a frame is mapped by one searchsorted instead of np.unique over
    61k pixels. Training records every episode (the best one is only known
    afterwards), so per-frame cost matters."""

    def __init__(self):
        super().__init__()
        self._sorted_keys = np.empty(0, dtype=np.uint32)
        self._sorted_idx = np.empty(0, dtype=np.uint8)

    def _refresh(self):
        items = sorted(self._palette.items())
        self._sorted_keys = np.array([k for k, _ in items], dtype=np.uint32)
        self._sorted_idx = np.array([i for _, i in items], dtype=np.uint8)

    def write_frame(self, obs: np.ndarray, mario=None) -> None:
        self._note_mario(mario)
        frame = np.asarray(obs)
        if len(self._sorted_keys):
            packed = (frame[..., 0].astype(np.uint32) << 16
                      | frame[..., 1].astype(np.uint32) << 8
                      | frame[..., 2].astype(np.uint32))
            pos = np.searchsorted(self._sorted_keys, packed)
            pos[pos == len(self._sorted_keys)] = 0
            if np.array_equal(self._sorted_keys[pos], packed):
                self._frames.append(self._sorted_idx[pos])
                return
        self._mario.pop()   # the base class notes it again
        super().write_frame(obs, mario)
        self._refresh()


class _Network:
    """One network's episode loop state: weights, best-so-far, the frames
    held for the not-yet-superseded latest episode."""

    def __init__(self, tag: str, group: str, label: str, keep_every: bool,
                 shuffle_seed: int | None, weights=None, first_episode: int = 0):
        self.tag, self.group, self.label = tag, group, label
        self.keep_every = keep_every
        self.shuffle_seed = shuffle_seed
        self.weights = weights
        self.next_episode = first_episode
        self.best_max_x = -1
        self.best_number: int | None = None
        self.held: tuple | None = None           # (number, FrameStore, slug): latest episode, unwritten
        self.reasons: dict[int, set] = {}        # run number -> why its frames are kept
        self.paths: dict[int, Path] = {}         # run number -> npz on disk


def _write_frames(recorder: FrameStore, path: Path) -> str | None:
    written = recorder.close(path)
    return str(written) if written else None


def _episode_spec_dict(base_number: int, net: _Network, settings, frame_cap: int, cfg_lr: float) -> dict:
    return {"ref": base_number,
            "overrides": {"shuffle_seed": net.shuffle_seed,
                          "learning_rate": (settings.learning_rate if settings.learning_rate is not None
                                            else cfg_lr),
                          "max_frames": frame_cap}}


def run_training(project, settings, emit=lambda *a: None, should_stop=lambda: False,
                 seed: int | None = None) -> dict:
    """Play the baseline, then `settings.episodes` learning episodes for the
    real network (and each shuffled control), all recorded through the run
    store. `project` is a ToolProject; `emit(kind, payload)` gets
    "phase"/"episode"/"done" events (the UI's live Learning chart);
    `should_stop()` cancels between and within episodes. Returns a summary.
    """
    import run_steering as rs
    from sim.project_runner import run_from_config

    name = project.name
    if project.is_read_only:
        raise PermissionError(f"project {name!r} is read-only; duplicate it to train")
    config = project.config
    ts = project.tool_settings
    seed = ts.experiment.seeds[0] if seed is None else seed
    frame_cap = settings.frame_cap
    ckpt_dir = PROJECTS_ROOT / name / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    def ep_config(lr):
        cfg = dataclasses.replace(config, scenario=dataclasses.replace(config.scenario, max_frames=frame_cap))
        if lr is not None:
            cfg = dataclasses.replace(cfg, mushroom_body=dataclasses.replace(
                cfg.mushroom_body, learning_rate=lr))
        return cfg

    env = rs.make_env(config.scenario.level)
    death_frames = ts.render.death_animation_frames

    state_env = None   # a second env for saved-state episodes: no warm-up backup, replays the action log

    def play(net: _Network, slug: str, lr, cfg, ep_seed=seed, state=None):
        nonlocal state_env
        recorder = PaletteFrameStore()
        if state is None:
            run_env = {"env": env, "warmup_frames": WARMUP_FRAMES}
            start_actions = None
        else:
            if state_env is None:
                state_env = rs.make_env(config.scenario.level)
            run_env = {"env": state_env}
            start_actions = state["actions"]
        tel, info = run_from_config(
            cfg, f"{slug}.mp4", seed=ep_seed, record_video=False, frame_skip=1,
            event_proximal_dopamine=settings.event_proximal,
            powerup_reward=ts.fitness.powerup > 0, gap_reward=ts.fitness.gap > 0,
            shuffle_seed=net.shuffle_seed, start_actions=start_actions,
            savestate=run_env,
            mb_weights=net.weights,
            on_frame=lambda f, obs, row: recorder.write_frame(obs, (row.get("mario_sx"), row.get("mario_y"))),
            should_stop=should_stop, death_animation_frames=death_frames)
        return recorder, info

    # ---- baseline: the untrained network, learning off (rate 0) ----
    base_number = next_run_number(name)
    base_slug = f"{base_number:03d}_train_baseline"
    emit("phase", "baseline")
    base_net = _Network("baseline", GROUP_BASELINE, "baseline", False, None)
    base_cfg = ep_config(0.0)
    base_spec = _base_spec(project, base_cfg, seed, f"{base_slug}.mp4")
    recorder, info = play(base_net, base_slug, 0.0, base_cfg)
    info["cancelled"] = should_stop()
    info["raw_frames_path"] = _write_frames(recorder, resolve_run_path(base_cfg, base_slug + "_raw.npz"))
    weights_unused = info.pop("mb_weights", None)
    record_run(name, base_number, base_slug, seed, info, base_spec,
               extra={"group": GROUP_BASELINE, "training": {
                   "network": "baseline", "episode": -1, "max_x": info["max_x_abs"],
                   "died": bool(info["died_or_flagged"]), "flag": bool(info.get("flag_get")),
                   "score": info.get("score")}})
    write_run_note(name, base_number, base_slug, seed, base_cfg, ts, info)
    emit("episode", {"number": base_number, "group": GROUP_BASELINE, "network": "baseline",
                     "episode": -1, "max_x": info["max_x_abs"]})
    if info["cancelled"]:
        env.close()
        return {"baseline": base_number, "cancelled": True}

    # ---- held-out test: frozen weights on seeds never used for training ----
    test_seeds = tuple(settings.test_seeds) if settings.test_every > 0 else ()

    def test_frozen(net: _Network, episode: int) -> dict:
        """Runs the current weights with learning rate 0 (so neither reward nor punishment can
        change them, and `net.weights` is left untouched) on every test seed."""
        frozen = ep_config(0.0)
        results = []
        for s in test_seeds:
            if should_stop():
                break
            _tel, r = run_from_config(
                frozen, "test.mp4", seed=s, record_video=False, frame_skip=1, write_telemetry=False,
                event_proximal_dopamine=settings.event_proximal, shuffle_seed=net.shuffle_seed,
                powerup_reward=ts.fitness.powerup > 0, gap_reward=ts.fitness.gap > 0,
                savestate={"env": env, "warmup_frames": WARMUP_FRAMES},
                mb_weights=net.weights, should_stop=should_stop, death_animation_frames=0)
            results.append((s, int(r["max_x_abs"]), bool(r.get("flag_get"))))
        wins = sum(w for _, _, w in results)
        record = {"network": net.label, "episode": episode, "baseline": base_number,
                  "seeds": [s for s, _, _ in results], "max_x": [x for _, x, _ in results],
                  "wins": wins, "win_rate": wins / len(results) if results else 0.0,
                  "mean_max_x": sum(x for _, x, _ in results) / len(results) if results else 0.0}
        if results and not should_stop():
            _append_eval(name, record)
        return record

    # ---- networks ----
    first = 0
    real_weights = None
    if settings.checkpoint:
        real_weights = np.load(ckpt_dir / settings.checkpoint)
        first = _checkpoint_episode(settings.checkpoint) + 1
    nets = [_Network("real", GROUP_REAL, "real", True, None, real_weights, first)]
    if settings.include_shuffled:
        for n in range(1, settings.n_shuffled + 1):
            nets.append(_Network(f"shuf{n}", group_for_shuffled(n), f"shuffled {n}", False, n))
    for net in nets:
        emit("phase", net.label)
        net_cfg = ep_config(settings.learning_rate)
        cancelled = False
        if test_seeds and net.tag == "real":
            emit("test", test_frozen(net, net.next_episode - 1))   # the starting brain, for reference
        for i in range(settings.episodes):
            if should_stop():
                cancelled = True
                break
            ep = net.next_episode
            number = next_run_number(name)
            slug = f"{number:03d}_train_{net.tag}_ep{ep:03d}"
            ep_seed = episode_seed(settings, seed, ep)
            start_name = pick_start_state(settings, ep_seed)
            state = None if start_name in (None, POWER_ON) else load_state(name, start_name)
            recorder, info = play(net, slug, settings.learning_rate, net_cfg, ep_seed, state)
            cancelled = should_stop()
            net.weights = info.pop("mb_weights")
            is_last = i == settings.episodes - 1
            reasons = set()
            if net.keep_every and ep % EVERY_NTH == 0:
                reasons.add("tenth")
            if info["max_x_abs"] > net.best_max_x:
                reasons.add("best")
            if is_last or cancelled:
                reasons.add("last")
            info["cancelled"] = cancelled
            info["raw_frames_path"] = None
            record_run(name, number, slug, ep_seed, info,
                       _episode_spec_dict(base_number, net, settings, frame_cap,
                                          config.mushroom_body.learning_rate),
                       extra={"group": net.group, "training": {
                           "network": net.label, "episode": ep, "max_x": info["max_x_abs"],
                           "died": bool(info["died_or_flagged"]), "flag": bool(info.get("flag_get")),
                           "score": info.get("score"), "seed": ep_seed, "start_state": start_name,
                           "baseline": base_number}})
            _apply_keep_policy(name, net, number, reasons, recorder, info, base_cfg, slug)
            net.next_episode += 1
            if net.tag == "real" and (ep % EVERY_NTH == 0 or is_last or cancelled):
                np.save(ckpt_dir / f"{net.tag}_ep{ep:03d}.npy", net.weights)
            emit("episode", {"number": number, "group": net.group, "network": net.label,
                             "episode": ep, "max_x": info["max_x_abs"]})
            if cancelled:
                break
            if test_seeds and ((ep + 1) % settings.test_every == 0 or is_last):
                emit("test", test_frozen(net, ep))
        _flush_held(name, net, base_cfg)
        if cancelled:
            break
    env.close()
    if state_env is not None:
        state_env.close()
    emit("done", {"cancelled": should_stop()})
    return {"baseline": base_number, "cancelled": should_stop(),
            "best": {n.label: n.best_max_x for n in nets}}


def _apply_keep_policy(name, net, number, reasons, recorder, info, base_cfg, slug):
    """Write this episode's frames if it has a reason, delete the previous
    best's frames if it lost that reason, 
    ("last" is known when the episode count is reached or Cancel is hit)."""
    prev_best = net.best_number
    if "best" in reasons:
        net.best_max_x = info["max_x_abs"]
        net.best_number = number
        if prev_best is not None:
            _drop_reason(name, net, prev_best, "best")
    net.held = None if reasons else (number, recorder, slug)
    if reasons:
        net.reasons[number] = reasons
        path = resolve_run_path(base_cfg, slug + "_raw.npz")
        written = _write_frames(recorder, path)
        if written:
            net.paths[number] = Path(written)
            patch_run(name, number, summary={"raw_frames_path": written})


def _flush_held(name, net, base_cfg):
    """Training stopped (count reached or Cancel): the latest episode is the
    last one, so its frames are kept even if they had no other reason."""
    if net.held is None:
        return
    number, recorder, slug = net.held
    net.held = None
    written = _write_frames(recorder, resolve_run_path(base_cfg, slug + "_raw.npz"))
    if written:
        net.reasons[number] = {"last"}
        net.paths[number] = Path(written)
        patch_run(name, number, summary={"raw_frames_path": written})


def _drop_reason(name, net, number, reason):
    reasons = net.reasons.get(number)
    if not reasons:
        return
    reasons.discard(reason)
    if not reasons:
        path = net.paths.pop(number, None)
        if path is not None and path.exists():
            path.unlink()
        patch_run(name, number, summary={"raw_frames_path": None})
        net.reasons.pop(number, None)


POWER_ON = "power-on"


def pick_start_state(settings, ep_seed: int):
    """The curriculum's start state for an episode (docs/SPEC_learning_v3.md A5): one of
    `settings.start_states`, chosen with the episode's own seeded rng so a run is reproducible.
    None when no curriculum is set (power-on, as always)."""
    if not settings.start_states:
        return None
    return settings.start_states[int(np.random.default_rng(ep_seed).integers(len(settings.start_states)))]


def episode_seed(settings, base_seed: int, episode: int) -> int:
    """The noise seed of training episode `episode` (docs/SPEC_learning_v2.md section 1):
    the base seed in "fixed" mode; the episode-th seed counting up from the base in "vary"
    mode, skipping any held-out test seed so training never sees a test seed."""
    base = settings.seed_base if settings.seed_base is not None else base_seed
    if settings.seed_mode == "fixed":
        return base
    held_out = set(settings.test_seeds) if settings.test_every > 0 else set()
    seed, n = base, 0
    while True:
        if seed not in held_out:
            if n == episode:
                return seed
            n += 1
        seed += 1


def _checkpoint_episode(filename: str) -> int:
    """Episode a real_epNNN.npy checkpoint was saved at. A play_NNN.npy (saved by a Play with
    keep-learning on) has no training episode: -1, so resuming from it starts at episode 0."""
    stem = Path(filename).stem
    return int(stem.rsplit("_ep", 1)[1]) if "_ep" in stem else -1


def checkpoint_dir(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name / "checkpoints"


def list_checkpoints(project_name: str) -> list[str]:
    """real_epNNN.npy (training) then play_NNN.npy (a Play that kept learning)."""
    d = checkpoint_dir(project_name)
    if not d.exists():
        return []
    return sorted(p.name for p in d.glob("real_ep*.npy")) + sorted(p.name for p in d.glob("play_*.npy"))


def load_checkpoint(project_name: str, filename: str):
    path = checkpoint_dir(project_name) / filename
    if not path.exists():
        raise FileNotFoundError(f"checkpoint {filename!r} not found under {checkpoint_dir(project_name)}")
    return np.load(path)


def save_play_checkpoint(project_name: str, run_number: int, weights) -> str:
    """Never overwrites a training checkpoint: it has its own play_<run number>.npy name."""
    d = checkpoint_dir(project_name)
    d.mkdir(parents=True, exist_ok=True)
    name = f"play_{run_number:03d}.npy"
    np.save(d / name, weights)
    return name


def eval_path(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name / EVAL_FILE


def load_evals(project_name: str) -> list[dict]:
    path = eval_path(project_name)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _append_eval(project_name: str, record: dict) -> None:
    path = eval_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(load_evals(project_name) + [record], indent=1), encoding="utf-8")


def _base_spec(project, cfg, seed, out_filename) -> dict:
    from tool.core.run_spec import RunSpec
    return RunSpec(project_name=project.name, config=cfg, tool_settings=project.tool_settings,
                   seed=seed, out_filename=out_filename).to_dict()


def run_training_streaming(project, settings, event_queue, stop_event) -> None:
    """Child-process entry point (the GUI spawns it, like runner.
    run_one_streaming). `project` is the window's live ToolProject, so
    unsaved config edits (a module toggle) are what trains."""
    try:
        t0 = time.time()
        result = run_training(project, settings,
                              emit=lambda kind, payload: event_queue.put((kind, payload)),
                              should_stop=stop_event.is_set)
        result["seconds"] = time.time() - t0
        event_queue.put(("finished", result))
    except Exception as exc:  # the parent must learn training failed, not hang
        import traceback
        event_queue.put(("error", f"{exc}\n{traceback.format_exc()}"))
