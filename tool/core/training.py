# What this file does, in plain English:
# Trains the fly's mushroom body (its learning centre) by playing level 1-1
# over and over from the same start, carrying the learned weights from one
# episode to the next. Every episode -- the untrained baseline, each
# training episode, and the optional shuffled-wiring control networks -- is
# recorded through the tool's run store, so it shows up in the Player and
# the Learning chart. Video frames are kept only for a few episodes to save
# disk; telemetry is kept for all.
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
import time
from pathlib import Path

import numpy as np

from config.output_routing import PROJECTS_ROOT, resolve_run_path
from tool.core.frame_store import FrameStore
from tool.core.run_store import (list_runs, next_run_number, patch_run, record_run,
                                 write_run_note)

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

    def write_frame(self, obs: np.ndarray) -> None:
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
        super().write_frame(obs)
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

    def play(net: _Network, slug: str, lr, cfg):
        recorder = PaletteFrameStore()
        tel, info = run_from_config(
            cfg, f"{slug}.mp4", seed=seed, record_video=False, frame_skip=1,
            event_proximal_dopamine=settings.event_proximal,
            shuffle_seed=net.shuffle_seed,
            savestate={"env": env, "warmup_frames": WARMUP_FRAMES},
            mb_weights=net.weights,
            on_frame=lambda f, obs, row: recorder.write_frame(obs),
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
                   "died": bool(info["died_or_flagged"]), "flag": bool(info.get("flag_get"))}})
    write_run_note(name, base_number, base_slug, seed, base_cfg, ts, info)
    emit("episode", {"number": base_number, "group": GROUP_BASELINE, "network": "baseline",
                     "episode": -1, "max_x": info["max_x_abs"]})
    if info["cancelled"]:
        env.close()
        return {"baseline": base_number, "cancelled": True}

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
        for i in range(settings.episodes):
            if should_stop():
                cancelled = True
                break
            ep = net.next_episode
            number = next_run_number(name)
            slug = f"{number:03d}_train_{net.tag}_ep{ep:03d}"
            recorder, info = play(net, slug, settings.learning_rate, net_cfg)
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
            record_run(name, number, slug, seed, info,
                       _episode_spec_dict(base_number, net, settings, frame_cap,
                                          config.mushroom_body.learning_rate),
                       extra={"group": net.group, "training": {
                           "network": net.label, "episode": ep, "max_x": info["max_x_abs"],
                           "died": bool(info["died_or_flagged"]), "flag": bool(info.get("flag_get")),
                           "baseline": base_number}})
            _apply_keep_policy(name, net, number, reasons, recorder, info, base_cfg, slug)
            net.next_episode += 1
            if net.tag == "real" and (ep % EVERY_NTH == 0 or is_last or cancelled):
                np.save(ckpt_dir / f"{net.tag}_ep{ep:03d}.npy", net.weights)
            emit("episode", {"number": number, "group": net.group, "network": net.label,
                             "episode": ep, "max_x": info["max_x_abs"]})
            if cancelled:
                break
        _flush_held(name, net, base_cfg)
        if cancelled:
            break
    env.close()
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


def _checkpoint_episode(filename: str) -> int:
    return int(Path(filename).stem.rsplit("_ep", 1)[1])


def list_checkpoints(project_name: str) -> list[str]:
    d = PROJECTS_ROOT / project_name / "checkpoints"
    return sorted(p.name for p in d.glob("real_ep*.npy")) if d.exists() else []


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
