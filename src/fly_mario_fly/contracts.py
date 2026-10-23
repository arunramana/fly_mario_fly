"""Shared types for every lane. Types only, no logic. Imports nothing from fly_mario_fly."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Protocol, runtime_checkable

# ---- Mario side (GIVEN 2) -------------------------------------------------

@dataclass(frozen=True)
class Box:
    """Axis-aligned rectangle in level pixels."""
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class MarioState:
    """Mario's body and status, read from RAM."""
    x: float
    y: float
    w: float
    h: float
    airborne: bool
    power: str
    facing: int


@dataclass(frozen=True)
class ObjectInstance:
    """One object found in the current frame, relative to Mario."""
    type: str
    id: int
    box: Box
    side: Literal["ahead", "behind", "above", "below"]
    state: dict = field(default_factory=dict)


@runtime_checkable
class ObjectType(Protocol):
    """A kind of Mario object (Goomba, pipe, pit...) that RAM can find and the env can remove."""
    name: str
    label: str
    note: str
    kind: Literal["enemy", "obstacle", "pickup", "terrain"]
    default_loom_shape: str
    block_hit_tile: Optional[str] = None     # key in facts["tiles"]: an instance in that tile id is a block the run hit
    causes_fall_death: bool = False          # Mario dying beside one of these fell in

    def find(self, ram: Any, facts: Any) -> list[ObjectInstance]: ...
    def remove(self, env: Any) -> None: ...


# ---- Sense (bridge in) ----------------------------------------------------

@dataclass(frozen=True)
class KnobSpec:
    """One user-visible, optionally evolvable number, with its range and where it comes from."""
    key: str
    label: str
    lo_label: str
    hi_label: str
    default: float
    lo: float
    hi: float
    scale: Literal["linear", "log"] = "linear"
    origin: Literal["fly", "invented"] = "invented"
    evolvable: bool = True
    floor: Optional[float] = None
    kind: Literal["slider", "switch"] = "slider"      # a switch is off/on: lo_label / hi_label name the two states


@dataclass(frozen=True)
class CalcStep:
    """One line of a sense's worked calculation, shown to the user."""
    label: str
    formula: str
    value: float
    norm: float
    group: Optional[str] = None


@dataclass(frozen=True)
class OverlayItem:
    """One shape the renderer draws over the game frame."""
    kind: Literal["box", "line", "dot", "wedge"]
    geometry: tuple
    colour: str
    line: Literal["solid", "dotted", "dashed"] = "solid"
    anchor: Literal["level", "screen_right"] = "level"   # level pixels, or pinned to the screen's right edge


@dataclass(frozen=True)
class SenseOutput:
    """What a sense returns each frame: neuron drive, what to draw, modifiers, and the working."""
    inputs: dict = field(default_factory=dict)      # neuron group name -> float
    overlay: list = field(default_factory=list)     # list[OverlayItem]
    modifiers: dict = field(default_factory=dict)   # name -> float
    steps: list = field(default_factory=list)       # list[CalcStep]


@runtime_checkable
class Sense(Protocol):
    """Bridge in: turns Mario objects into drive onto fly mechanisms. A per_object sense works on ANY object type."""
    name: str
    label: str
    effect: str
    scope: Literal["per_object", "whole_fly"]
    colour: str
    line: Literal["solid", "dotted", "dashed"]
    feeds: list
    knobs: list
    raises: list      # names of modifiers it sets for other senses and actions
    reads: list       # names of modifiers it reads from other senses

    def cue(self, objects: list, mario: MarioState, facts: Any, knobs: dict, memory: Any) -> SenseOutput: ...


@runtime_checkable
class LoomShape(Protocol):
    """Turns an object into the box whose angular size the looming sense measures."""
    name: str
    label: str
    description: str
    knobs: list

    def shape(self, obj: ObjectInstance, facts: Any, knobs: dict) -> Box: ...


# ---- Fly side (GIVEN 1) ---------------------------------------------------

@runtime_checkable
class Mechanism(Protocol):
    """A fly circuit built from real MaleCNS wiring only; knows nothing about Mario."""
    name: str
    label: str
    input_groups: list
    output_groups: list
    neuron_sets: list


# ---- Action (bridge out) --------------------------------------------------

@dataclass(frozen=True)
class ButtonIntent:
    """Which NES buttons an action wants pressed or released this frame, and how strongly it insists."""
    press: frozenset = frozenset()
    release: frozenset = frozenset()
    priority: int = 0


@runtime_checkable
class Action(Protocol):
    """Bridge out: reads fly neuron rates and decides one button's intent."""
    name: str
    label: str
    button: str
    source_groups: list
    knobs: list
    priority: int
    reads: list       # names of modifiers it reads from the senses

    def decide(self, rates: dict, knobs: dict, state: Any) -> ButtonIntent: ...


# ---- Scenes ---------------------------------------------------------------

@runtime_checkable
class SceneModifier(Protocol):
    """Edits the game at reset or every frame (remove an enemy, add a pit...) to build a test scene."""
    name: str
    label: str
    description: str
    params: list

    def on_reset(self, env: Any, p: dict) -> None: ...
    def on_frame(self, env: Any, p: dict) -> None: ...


@dataclass(frozen=True)
class Scene:
    """A reproducible test situation: level, modifiers, start point, noise, and stop rules."""
    level_id: str
    rom: str = "v0"
    modifiers: tuple = ()                 # ((modifier name, params dict), ...)
    start: Any = "level_start"            # "level_start" | x pixel (int) | moment id (str)
    noop: int = 0
    sigma: float = 0.0
    seed: int = 0
    max_frames: int = 6000
    stuck_frames: int = 300               # counted only after Mario's first move


# ---- Fly config, moments, runs --------------------------------------------

@dataclass(frozen=True)
class FlyConfig:
    """A complete fly: which senses attach to which objects, which actions are on, and the knob values."""
    name: str
    attachments: dict = field(default_factory=dict)   # sense name -> set of object type names
    loom_shapes: dict = field(default_factory=dict)   # object type name -> shape name
    whole_fly: frozenset = frozenset()                # whole_fly sense names that are on
    actions: frozenset = frozenset()                  # action names that are on
    knobs: dict = field(default_factory=dict)         # knob key -> float
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SavedMoment:
    """A rewindable snapshot: emulator, brain and sense memory, enough to resume the run exactly."""
    id: str
    run_id: str
    name: str
    frame: int
    x: float
    auto: bool
    emulator_state: bytes
    brain_state: dict          # MaleCNS body id -> rate
    sense_memory: Any
    rng_state: Any
    scene: Scene
    fly: FlyConfig


@dataclass(frozen=True)
class RunRequest:
    """Ask the runner to play a fly on a scene, optionally resuming from a saved moment."""
    fly: FlyConfig
    scene: Scene
    from_moment: Optional[str] = None


@dataclass(frozen=True)
class RunResult:
    """What a finished run reports: outcome, progress, counts, saved moments, and a reproducibility hash."""
    id: str
    fly: str
    scene: Scene
    parent_moment: Optional[str]
    outcome: Literal["flag", "died", "stuck", "timeout"]
    death: Optional[dict]
    max_x: float
    score: float
    blocks: int
    mushroom: bool
    counts: dict = field(default_factory=dict)
    moments: list = field(default_factory=list)
    hash: str = ""
