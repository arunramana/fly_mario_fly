"""One run: the frame loop that joins Mario to the fly.

One frame:  RAM -> Mario's objects -> the attached senses -> drive onto the fly brain -> neuron rates ->
            the actions' button intents -> buttons -> the emulator.
Nothing here decides what the fly does. The senses change what the circuit sees; the actions read what the
circuit did; this file only passes the numbers along and applies the priorities the actions declared.

LEGACY (Options.legacy): the three quirks of the old tool that the parity test needs, all off by default:
  * the stuck rule counts from frame 0 of the episode (idle frames included) instead of from Mario's first move;
  * max_frames counts the idle frames too;
  * a button set with no Left or Right is replaced by no buttons at all (the old tool had no bare-A combo).
"""
from __future__ import annotations

import copy
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np

from fly_mario import registry
from fly_mario.contracts import ButtonIntent, FlyConfig, RunResult, SavedMoment, Scene
from fly_mario.fly.brain import RateModel, build_brain
from fly_mario.mario import ram as R
from fly_mario.mario import walker
from fly_mario.mario.env import MarioEnv, button_byte
from fly_mario.runner import config as C
from fly_mario.runner import moments as M
from fly_mario.senses.kit.memory import SenseMemory

_BRAINS: dict = {}


def get_brain(spec):
    """Brains are big and read-only: build/load once per process and mechanism set."""
    if spec not in _BRAINS:
        _BRAINS[spec] = build_brain(spec)
    return _BRAINS[spec]


@dataclass(frozen=True)
class Options:
    legacy: bool = False
    record_ram: bool = False
    moment_every_s: float = 2.0          # auto-saved moment every N seconds of play (0 = off); needs Run(moments=True)
    moment_before_death_s: float = 3.0   # the "before death" moment is the newest one at least this far before the death
    keep_auto: int = 20                  # auto moments kept per run (the oldest rotate away; manual and death ones stay)


FPS = 60                                 # NES frames per second
RING_EVERY = 30                          # frames between the in-memory snapshots the "before death" moment is picked from


@dataclass
class FrameRecord:
    """Everything that happened in one frame, for the renderer and the recorder."""
    frame: int                  # counted from the start of the episode, idle frames included
    x: int                      # Mario's world x after the frame
    mario: object               # MarioState before the frame
    airborne: bool
    buttons: frozenset
    outputs: dict               # sense name -> SenseOutput
    rates: dict                 # neuron group -> mean rate
    intents: dict               # action name -> ButtonIntent
    mods: dict                  # modifiers raised by the senses this frame
    screen: np.ndarray          # the picture AFTER the frame's action
    done: bool = False
    moments: list = field(default_factory=list)    # MomentInfo saved during this frame (auto, or the one before a death)
    # What the senses looked at this frame, for the renderer and the API (read from the RAM BEFORE the action).
    found: dict = field(default_factory=dict)      # object type -> [ObjectInstance]: type, id, box (level px), side, state
    scroll_x: int = 0           # level x of the screen's left edge in that RAM; subtract it from level-pixel overlays
                                # and draw them on the previous frame's screen (or on `screen` with scroll_x_after)
    scroll_x_after: int = 0     # the same, after the action: the offset that matches `screen`

    @property
    def objects(self) -> list:
        """Every object found this frame, all types in one list (types sorted, as found)."""
        return [o for objs in self.found.values() for o in objs]


def screen_scroll(ram, facts) -> int:
    """Level x (pixels) of the screen's left edge: add it to a screen x to get a level x, subtract it to go back."""
    r = facts["ram"]
    return int(ram[r["screen_page"]]) * 256 + int(ram[r["screen_x"]])


def resolve_buttons(intents) -> frozenset:
    """Per button, the highest-priority intent that names it wins; a release beats a press of equal priority."""
    best: dict = {}
    for it in intents:
        for names, pressed in ((it.release, 0), (it.press, 1)):
            for b in names:
                key = (it.priority, 1 - pressed)
                if b not in best or key > best[b][0]:
                    best[b] = (key, bool(pressed))
    return frozenset(b for b, (_, pressed) in best.items() if pressed)


def legacy_buttons(buttons: frozenset) -> frozenset:
    """The old tool's action list had only NOOP, R, R+A, L, L+A: a set with no direction became NOOP."""
    return buttons if buttons & {"left", "right"} else frozenset()


class Run:
    def __init__(self, fly: FlyConfig, scene: Optional[Scene] = None, options: Options = Options(),
                 env: Optional[MarioEnv] = None, run_id: str = "", from_moment: Optional[str] = None,
                 moments: bool = False):
        """`from_moment`: resume from a saved moment (id) with this fly, which may differ from the moment's own.
        The scene defaults to the moment's. `moments`: write auto / before-death moments to the store as it plays."""
        C.validate(fly, strict_range=False)
        self._resume = M.get_moment(from_moment) if from_moment else None
        if scene is None:
            if self._resume is None:
                raise ValueError("a Run needs a scene (or a moment to resume from)")
            scene = self._resume.scene
        if self._resume is not None and (scene.level_id, scene.rom) != (self._resume.scene.level_id, self._resume.scene.rom):
            raise ValueError(f"moment {from_moment} is on {self._resume.scene.level_id}/{self._resume.scene.rom}, "
                             f"not {scene.level_id}/{scene.rom}")
        if moments and not run_id:
            raise ValueError("moments=True needs a run_id: the moments live in the run's folder")
        self.fly, self.scene, self.options, self.run_id = fly, scene, options, run_id
        self.parent = from_moment
        self.store_moments = moments
        self.seen: set = set()                   # object types found at any point of the run
        self._ring: deque = deque(maxlen=int(options.moment_before_death_s * FPS / RING_EVERY) + 3)
        self.env = env or MarioEnv()
        self.knobs = C.resolve_knobs(fly)
        self.senses = C.active_senses(fly)
        self.actions = C.active_actions(fly)
        self.brain = get_brain(C.brain_spec(fly))
        self.model = RateModel()
        self.objects = registry.list_plugins("objects")
        self.scene_mods = [(registry.list_plugins("scenes")[n], dict(p)) for n, p in scene.modifiers]
        self.rows: list = []
        self.rates: dict = defaultdict(list)
        self.replay: list = []                   # every button byte sent to the emulator, idle frames included
        self.rams: list = []
        self.moments: list = []
        self.started = False
        self.finished = False
        self.outcome = "timeout"
        self.death = None

    def close(self) -> None:
        """Free the emulator. Call when the run is over or abandoned; the Run is not played after this."""
        self.env.close()

    # ---- start ----------------------------------------------------------------------------------------
    def start(self) -> None:
        sc, env = self.scene, self.env
        if self._resume is not None:
            self.restore(self._resume)
            self._remember()
            return
        env.reset(sc.level_id, sc.rom, 0)
        for mod, p in self.scene_mods:
            mod.on_reset(env, p)
        if isinstance(sc.start, int):
            walker.walk_to(env, sc.start)
        for _ in range(sc.noop):                 # idle frames: the fly has not taken over yet and sees nothing
            self._send(frozenset())
        self.rng = np.random.default_rng(sc.seed)
        self.memory = {s.name: SenseMemory() for s in self.senses}
        self.astate = {a.name: {} for a in self.actions}
        self.h = self.brain.new_state()
        self.frame = 0                           # fly frames played
        self.max_x = self.x0 = R.mario_x(env.ram, env.facts)
        self.best_frame = 0                      # legacy: absolute frame of the last new max x
        self.last_progress = 0                   # fly frame of the last new max x (0 = the start)
        self.moved = False
        self.hit_blocks: set = set()
        self.big_seen = False
        self.counts = defaultdict(int)
        self._prev_a = self._prev_left = False
        self.started = True
        self._remember()

    def _send(self, buttons):
        self.replay.append(button_byte(buttons))
        return self.env.step(sorted(buttons))

    # ---- one frame ------------------------------------------------------------------------------------
    def step(self) -> FrameRecord:
        if not self.started:
            self.start()
        env, fly, sc = self.env, self.fly, self.scene
        for mod, p in self.scene_mods:
            mod.on_frame(env, p)
        facts, ram = env.facts, env.ram
        scroll_before = screen_scroll(ram, facts)
        mario = R.read_mario(ram, facts)
        found = {name: p.find(ram, facts) for name, p in self.objects.items()}
        world = [o for objs in found.values() for o in objs]

        mods: dict = {}
        outputs: dict = {}
        inputs = defaultdict(float)
        for s in self.senses:
            mem = self.memory[s.name]
            mem.rng, mem.sigma, mem.world, mem.mods = self.rng, sc.sigma, world, mods
            if s.scope == "whole_fly":
                objs = world
            else:
                attached = fly.attachments.get(s.name, ())
                objs = [self._annotated(o) for o in world if o.type in attached]
            out = s.cue(objs, mario, facts, self.knobs, mem)
            outputs[s.name] = out
            mods.update(out.modifiers)
            for g, v in out.inputs.items():
                inputs[g] += v
        self.h = self.brain.advance(self.h, self.brain.drive(inputs), self.model)
        rates = self.brain.rates(self.h)

        intents = {}
        for a in self.actions:
            st = self.astate[a.name]
            st["airborne"], st["mods"] = mario.airborne, mods
            intents[a.name] = a.decide(rates, self.knobs, st)
        buttons = resolve_buttons(intents.values())
        if self.options.legacy:
            buttons = legacy_buttons(buttons)

        self.seen |= {n for n, objs in found.items() if objs}
        if self.options.record_ram:
            self.rams.append(np.array(ram, copy=True))
        self._tally(buttons, found, mario)
        st = self._send(buttons)
        x = int(st.info.get("x_pos", mario.x))
        rec = FrameRecord(self.scene.noop + self.frame, x, mario, mario.airborne, buttons, outputs, rates, intents,
                          dict(mods), st.frame, found={k: list(v) for k, v in found.items()}, scroll_x=scroll_before,
                          scroll_x_after=screen_scroll(env.ram, env.facts))
        self._log(rec, st)
        self._advance(x, st, found, mario)
        rec.done = self.finished
        rec.moments = self._auto_moments()
        return rec

    def _annotated(self, o):
        shape = self.fly.loom_shapes.get(o.type)
        return replace(o, state={**o.state, "loom_shape": shape}) if shape else o

    def _tally(self, buttons, found, mario) -> None:
        a, left = "A" in buttons, "left" in buttons
        self.counts["a_onsets"] += int(a and not self._prev_a)
        self.counts["left_presses"] += int(left and not self._prev_left)
        self.counts["left_frames"] += int(left)
        self._prev_a, self._prev_left = a, left
        for name, p in self.objects.items():
            key = p.block_hit_tile          # declared by the plug-in; the tile id is a fact
            if key:
                tid = self.env.facts["tiles"][key]
                self.hit_blocks |= {int(o.box.x) for o in found.get(name, ()) if o.state.get("tile") == tid}
        self.big_seen |= mario.power != "small"
        self._last_found, self._last_mario = found, mario

    def _log(self, rec: FrameRecord, st) -> None:
        row = {"frame": rec.frame, "x": rec.x, "feet_y": rec.mario.y + rec.mario.h, "airborne": int(rec.airborne),
               "buttons": "+".join(sorted(rec.buttons)) or "NOOP", "byte": button_byte(rec.buttons),
               "score": int(st.info.get("score", 0))}
        for name, out in rec.outputs.items():
            for s in out.steps:
                row[f"{name}.{s.label}"] = s.value
        for k, v in rec.mods.items():
            row[f"mod.{k}"] = v
        self.rows.append(row)
        for g, v in rec.rates.items():
            self.rates[g].append(v)

    def _advance(self, x: int, st, found, mario) -> None:
        sc, legacy = self.scene, self.options.legacy
        idx = self.frame                         # this frame's index among the fly's frames
        abs_frame = sc.noop + idx                # ... and among all frames, idle ones included
        if x > self.max_x:
            self.max_x, self.best_frame, self.last_progress = x, abs_frame, idx
        self.moved = self.moved or x != self.x0
        self.frame += 1
        self.score = int(st.info.get("score", 0))
        if st.info.get("flag_get"):
            self._finish("flag", x)
        elif st.done:
            self._finish("died", x)
        elif legacy and abs_frame - self.best_frame >= sc.stuck_frames:
            self._finish("stuck", x)                 # the old rule: counted from frame 0, before Mario ever moved
        elif not legacy and idx - self.last_progress >= sc.stuck_frames:
            self._finish("stuck", x)                 # counted from the start; a run that never moves is stuck too
        elif (abs_frame + 1 if legacy else self.frame) >= sc.max_frames:
            self._finish("timeout", x)

    def _finish(self, outcome: str, x: int) -> None:
        self.finished, self.outcome = True, outcome
        if outcome == "died":
            near = [(abs(o.box.x - self._last_mario.x), o.type) for objs in self._last_found.values() for o in objs
                    if self.objects[o.type].kind == "enemy"]
            near = [n for n in near if n[0] <= 20]
            fell = [n for n, p in self.objects.items() if p.causes_fall_death
                    and any(o.box.x - 12 <= x <= o.box.x + o.box.w + 12 for o in self._last_found.get(n, ()))]
            self.death = {"x": x, "cause": fell[0] if fell else (f"enemy:{min(near)[1]}" if near else "other")}

    # ---- whole run ------------------------------------------------------------------------------------
    def play(self, on_frame=None) -> RunResult:
        if not self.started:
            self.start()
        while not self.finished:
            rec = self.step()
            if on_frame is not None:
                on_frame(rec)
        return self.result()

    def result(self) -> RunResult:
        digest = hashlib.sha256(f"{self.scene.level_id}/{self.scene.rom}/".encode() + bytes(self.replay)).hexdigest()   # the trajectory, not the settings
        return RunResult(
            id=self.run_id, fly=self.fly.name, scene=self.scene, parent_moment=self.parent, outcome=self.outcome,
            death=self.death, max_x=float(self.max_x), score=float(getattr(self, "score", 0)),
            blocks=len(self.hit_blocks), mushroom=self.big_seen, counts={"frames": self.frame, **self.counts},
            moments=list(self.moments), hash=digest)

    # ---- saved moments --------------------------------------------------------------------------------
    def _capture(self, name: str = "", auto: bool = False) -> tuple:
        """(SavedMoment, object types on screen): everything needed to resume this run exactly, as of now."""
        blob = copy.deepcopy({
            "memory": {k: dict(m) for k, m in self.memory.items()}, "astate": self.astate, "frame": self.frame,
            "max_x": self.max_x, "x0": self.x0, "best_frame": self.best_frame, "last_progress": self.last_progress,
            "moved": self.moved, "hit_blocks": self.hit_blocks, "big_seen": self.big_seen, "counts": dict(self.counts),
            "prev": (self._prev_a, self._prev_left), "replay": list(self.replay), "score": getattr(self, "score", 0),
            "seen": set(self.seen)})
        m = SavedMoment(id=f"{self.run_id}@{self.frame}", run_id=self.run_id, name=name or f"frame {self.frame}",
                        frame=self.frame, x=float(self.max_x), auto=auto, emulator_state=self.env.save_state(),
                        brain_state=self.brain.get_state(self.h), sense_memory=blob,
                        rng_state=copy.deepcopy(self.rng.bit_generator.state), scene=self.scene, fly=self.fly)
        on_screen = tuple(sorted(n for n, objs in getattr(self, "_last_found", {}).items() if objs))
        return m, on_screen

    def snapshot(self, name: str = "", auto: bool = False) -> SavedMoment:
        """A moment of this run, in memory (moments.save_moment() puts one on disk)."""
        m, _ = self._capture(name, auto)
        self.moments.append(m.id)
        return m

    # ---- the moment store -----------------------------------------------------------------------------
    def _remember(self) -> None:
        """Take the first ring snapshot (the start of this run, or the frame it was resumed at)."""
        if self.store_moments:
            self._ring.append(self._capture())

    def capture_at(self, frame: Optional[int] = None) -> tuple:
        """(SavedMoment, on_screen) at `frame` (None = now): now, or one of the recent in-memory snapshots."""
        if frame is None or frame == self.frame:
            return self._capture()
        for cap in self._ring:
            if cap[0].frame == frame:
                return cap
        raise ValueError(f"frame {frame} is not available: the run is at frame {self.frame} and keeps a snapshot every "
                         f"{RING_EVERY} frames for only the last {self._ring.maxlen}")

    def _auto_moments(self) -> list:
        """After a frame: the auto moment if one is due, and the one before a death. Returns the MomentInfo saved."""
        if not self.store_moments:
            return []
        o, f, out = self.options, self.frame, []
        every = int(round(o.moment_every_s * FPS))
        if not self.finished and f > 0 and (f % RING_EVERY == 0 or (every and f % every == 0)):
            cap = self._capture()
            self._ring.append(cap)
            if every and f % every == 0:
                info = M.put_moment(cap[0], "auto", f"auto, frame {f}", cap[1])
                self.moments.append(info.id)
                M.rotate_auto(self.run_id, o.keep_auto)
                out.append(info)
        if self.finished and self.outcome == "died" and self._ring:
            target = f - int(round(o.moment_before_death_s * FPS))
            earlier = [c for c in self._ring if c[0].frame <= target]
            cap = earlier[-1] if earlier else self._ring[0]
            info = M.put_moment(cap[0], "death", f"{o.moment_before_death_s:g} s before death", cap[1])
            self.moments.append(info.id)
            out.append(info)
        return out

    def restore(self, m: SavedMoment) -> None:
        """Resume from a moment of this fly and scene (rows recorded so far are kept)."""
        self.env.load_state(m.emulator_state)
        b = copy.deepcopy(m.sense_memory)
        self.rng = np.random.default_rng(0)
        self.rng.bit_generator.state = copy.deepcopy(m.rng_state)
        self.memory = {s.name: SenseMemory(b["memory"].get(s.name, {})) for s in self.senses}
        self.astate = {a.name: b["astate"].get(a.name, {}) for a in self.actions}
        self.h = self.brain.set_state(m.brain_state)
        self.frame, self.max_x, self.x0 = b["frame"], b["max_x"], b["x0"]
        self.best_frame, self.last_progress, self.moved = b["best_frame"], b["last_progress"], b["moved"]
        self.hit_blocks, self.big_seen, self.counts = b["hit_blocks"], b["big_seen"], defaultdict(int, b["counts"])
        self._prev_a, self._prev_left = b["prev"]
        self.replay = list(b.get("replay", self.replay))
        self.score = b.get("score", 0)
        self.seen = set(b.get("seen", ()))
        self.started, self.finished = True, False
