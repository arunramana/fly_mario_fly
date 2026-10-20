"""JSON shapes for the browser (pydantic). Mirrors web/src/api/types.ts, with one deliberate difference:
knobs travel as slider positions (0..1) with lo/hi labels, never as raw values (see knobs.py).
Python sets/tuples are arrays on the wire."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

LineStyle = Literal["solid", "dotted", "dashed"]
Anchor = Literal["level", "screen_right"]
Position = Annotated[float, Field(ge=0.0, le=1.0)]


class Box(BaseModel):
    x: float
    y: float
    w: float
    h: float


class KnobUI(BaseModel):
    """A knob as the UI sees it: a slider. `position` is the default (in a registry entry) or the fly's setting."""
    key: str
    label: str
    lo_label: str
    hi_label: str
    position: Position
    scale: Literal["linear", "log"]
    origin: Literal["fly", "invented"]
    evolvable: bool
    floor_position: Optional[Position] = None


class ObjectInfo(BaseModel):
    name: str
    label: str
    note: str
    kind: Literal["enemy", "obstacle", "pickup", "terrain"]
    default_loom_shape: str


class SenseInfo(BaseModel):
    name: str
    label: str
    effect: str
    scope: Literal["per_object", "whole_fly"]
    colour: str
    line: LineStyle
    feeds: list[str]
    knobs: list[KnobUI]


class ShapeInfo(BaseModel):
    name: str
    label: str
    description: str
    handles: list[str]            # object types it applies to; empty = any
    knobs: list[KnobUI]


class ActionInfo(BaseModel):
    name: str
    label: str
    button: str
    source_groups: list[str]
    knobs: list[KnobUI]
    priority: int
    status: Literal["ready", "soon"] = "ready"


class SceneModifierInfo(BaseModel):
    name: str
    label: str
    description: str
    params: list[dict]
    per_object: bool


class SceneDTO(BaseModel):
    level_id: str
    rom: str = "v0"
    modifiers: list[tuple[str, dict]] = []
    start: Union[int, str] = "level_start"
    noop: int = 0
    sigma: float = 0.0
    seed: int = 0
    max_frames: int = 6000
    stuck_frames: int = 300


class TestScene(BaseModel):
    """A ready-made test situation built from a scene modifier and an object type."""
    name: str
    label: str
    scene: SceneDTO


class RegistryInfo(BaseModel):
    objects: list[ObjectInfo]
    senses: list[SenseInfo]
    shapes: list[ShapeInfo]
    actions: list[ActionInfo]
    scene_modifiers: list[SceneModifierInfo]
    test_scenes: list[TestScene]
    presets: list[str]            # names of the fly presets (GET /flies/presets)


class FlyDTO(BaseModel):
    name: str
    attachments: dict[str, list[str]] = {}
    loom_shapes: dict[str, str] = {}
    whole_fly: list[str] = []
    actions: list[str] = []
    knobs: dict[str, Position] = {}      # knob key -> slider position
    provenance: dict = {}


class FlySummary(BaseModel):
    name: str
    senses: list[str]
    actions: list[str]


class LevelInfo(BaseModel):
    id: str
    label: str
    kind: str                             # overground | underground | sky | water | castle | mixed
    status: Literal["open", "cleared", "locked"]    # cleared = some saved run reached the flag; nothing is locked yet
    status_text: str = "not tried"        # "not tried" | "won 2/5" | "best x 1840"
    scanned: bool = False                 # False: width and objects are unknown (not yet scanned or seen by any run)
    partial: bool = False                 # the scan stopped before the flag: width and objects are lower bounds
    width: Optional[int] = None           # level length in px (how far the scan got if partial); None = unknown
    objects: Optional[list[str]] = None   # object types present, scan plus every run's objects_seen; None = unknown


class RunRequestDTO(BaseModel):
    fly: FlyDTO
    scene: SceneDTO
    from_moment: Optional[str] = None


class RunResultDTO(BaseModel):
    id: str
    fly: str
    scene: SceneDTO
    parent_moment: Optional[str] = None
    outcome: Literal["flag", "died", "stuck", "timeout"]
    death: Optional[dict] = None
    max_x: float
    score: float
    blocks: int
    mushroom: bool
    counts: dict[str, float] = {}
    moments: list[str] = []
    hash: str = ""


class RunSummary(BaseModel):
    id: str
    fly: str
    level_id: str
    status: Literal["pending", "running", "finished", "aborted", "failed"]
    outcome: Optional[Literal["flag", "died", "stuck", "timeout"]] = None
    max_x: Optional[float] = None
    score: Optional[float] = None
    parent_moment: Optional[str] = None   # the moment this run was resumed from


class RunDetail(RunSummary):
    scene: Optional[SceneDTO] = None
    result: Optional[RunResultDTO] = None


class MomentSummary(BaseModel):
    """A saved moment without its emulator/brain bytes."""
    id: str
    run_id: str
    name: str
    frame: int
    x: float
    auto: bool                            # not saved by hand (kind auto or death)
    kind: Literal["manual", "auto", "death"] = "manual"
    scene: SceneDTO
    fly: FlyDTO
    on_screen: list[str] = []             # object types visible at this moment


class MomentRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MomentSave(BaseModel):
    """Save a moment of a running run. `frame` None = now; else one of the recent in-memory snapshots."""
    name: str = ""
    frame: Optional[int] = None


class TryDTO(BaseModel):
    """One run resumed from a moment. `change` is the fly's difference from the moment's fly, in words only."""
    run_id: str
    change: str
    outcome: str
    max_x: float


class OverlayItem(BaseModel):
    kind: Literal["box", "line", "dot", "wedge"]
    geometry: list[float]
    colour: str
    line: LineStyle
    anchor: Anchor = "level"


# ---- the live stream: server -> client --------------------------------------------------------------------------
class ObjectOnScreen(BaseModel):
    """An object the senses looked at this frame. `box` is in level pixels, like `mario`."""
    type: str
    id: int
    box: Box
    side: Literal["ahead", "behind", "above", "below"]


class FrameEvent(BaseModel):
    """One frame. The game picture and the overlay are separate layers; `rates` is the light state (0..1 per
    neuron group)."""
    type: Literal["frame"] = "frame"
    frame: int
    total: int
    frame_png: str                        # base64 PNG of the 256x240 game screen, nothing drawn on it
    mario: Box                            # in level pixels
    x: float
    buttons: list[str]
    overlay: list[OverlayItem]            # what the senses want drawn, in level pixels
    objects: list[ObjectOnScreen] = []    # every object found this frame (the same data the senses saw)
    scroll_x: int = 0                     # level x of the screen's left edge for mario/objects/overlay: subtract it
                                          # to get screen pixels (they are read before the frame's action)
    scroll_x_after: int = 0               # the same for frame_png itself, which shows the state after the action
    rates: dict[str, float]


class StateEvent(BaseModel):
    type: Literal["state"] = "state"
    paused: bool
    speed: float


class MomentEvent(BaseModel):
    type: Literal["moment"] = "moment"
    moment: MomentSummary


class EndEvent(BaseModel):
    type: Literal["end"] = "end"
    result: RunResultDTO


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


RunEvent = Union[FrameEvent, StateEvent, MomentEvent, EndEvent, ErrorEvent]


# ---- the live stream: client -> server --------------------------------------------------------------------------
class ClientMessage(BaseModel):
    """{"type": "play"|"pause"|"step"|"speed", "value": multiplier}  (speed 0 or >= 100 means as fast as possible)."""
    type: Literal["play", "pause", "step", "speed"]
    value: Optional[float] = None
