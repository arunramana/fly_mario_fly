"""JSON shapes for the browser (pydantic). Mirrors web/src/api/types.ts, with one deliberate difference:
knobs travel as slider positions (0..1) with lo/hi labels, never as raw values (see knobs.py).
Python sets/tuples are arrays on the wire."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

LineStyle = Literal["solid", "dotted", "dashed"]
Anchor = Literal["level", "screen_right"]
Position = Annotated[float, Field(ge=0.0, le=1.0)]


Dials = Literal["tuned", "original"]


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
    kind: Literal["slider", "switch"] = "slider"      # a switch is off (position 0) / on (position 1)


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
    order: int = 0                        # column order in the UI (the sense's own `order`)


class ShapeInfo(BaseModel):
    name: str
    label: str
    description: str
    knobs: list[KnobUI]


class ActionInfo(BaseModel):
    name: str
    label: str
    button: str
    source_groups: list[str]
    knobs: list[KnobUI]
    priority: int
    order: int = 0                        # button order in the UI (the registry's order)
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


class DialView(BaseModel):
    """One knob of a fly as the dials switch sees it: where evolution left it and where the hand-set original sits."""
    position: Position
    original_position: Position
    tuned: bool                           # position differs from original_position


class FlyView(FlyDTO):
    """A fly as the server returns it: the FlyDTO plus, for every knob any plug-in declares, its dial."""
    dials: dict[str, DialView] = {}


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
    scanned: bool = False                 # False: objects are unknown (not yet scanned or seen by any run)
    partial: bool = False                 # the scan stopped before the flag: objects are a lower bound
    objects: Optional[list[str]] = None   # object types present, scan plus every run's objects_seen; None = unknown


class RunRequestDTO(BaseModel):
    fly: FlyDTO
    dials: Dials = "tuned"                # "original" runs the fly with every knob at its hand-set default
    scene: SceneDTO
    from_moment: Optional[str] = None


class DeathDTO(BaseModel):
    """How a run ended in death: where, and what did it. `object_type`/`label` name the thing (null for "other")."""
    x: float
    kind: Literal["fall", "enemy", "other"]
    object_type: Optional[str] = None
    object_label: Optional[str] = None


class RunResultDTO(BaseModel):
    id: str
    fly: str
    scene: SceneDTO
    parent_moment: Optional[str] = None
    outcome: Literal["flag", "died", "stuck", "timeout"]
    death: Optional[DeathDTO] = None
    max_x: float
    score: float
    blocks: int
    mushroom: bool
    counts: dict[str, float] = {}
    moments: list[str] = []
    hash: str = ""
    dials: Dials = "tuned"                # which dials the run used


class RunSummary(BaseModel):
    id: str
    fly: str
    level_id: str
    status: Literal["pending", "running", "finished", "aborted", "failed"]
    outcome: Optional[Literal["flag", "died", "stuck", "timeout"]] = None
    max_x: Optional[float] = None
    score: Optional[float] = None
    parent_moment: Optional[str] = None   # the moment this run was resumed from
    dials: Dials = "tuned"                # which dials the run used


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
    frame_png: str                        # base64 PNG of the 256x240 game screen, nothing drawn on it: the screen the
                                          # senses were looking at (before this frame's action), so the overlay sits on it
    mario: Box                            # in level pixels
    x: float
    buttons: list[str]
    overlay: list[OverlayItem]            # what the senses want drawn, in level pixels
    objects: list[ObjectOnScreen] = []    # every object found this frame (the same data the senses saw)
    scroll_x: int = 0                     # level x of the screen's left edge for mario/objects/overlay: subtract it
                                          # to get screen pixels (they are read before the frame's action)
    scroll_x_after: int = 0               # the same after the action (frame_png shows the screen before it, as the videos do)
    rates: dict[str, float]
    overlay_png: Optional[str] = None     # base64 PNG, transparent: the senses overlay, cropped to what is drawn;
                                          # null = nothing to draw on this frame
    overlay_at: Optional[list[int]] = None  # [x, y] of the overlay's top-left on the 1024 x 960 game-at-x4 canvas
    brain_jpg: Optional[str] = None       # base64 JPEG, 896 x 1080: the R3 brain panel (glowing somata, nerve cord, LIVE
                                          # BRAIN, index). Sent only when a newer picture is ready (~10 per second):
                                          # null = keep showing the last one


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


# ---- background jobs (evolution, "test this fly") ---------------------------------------------------------------
TestDials = Literal["tuned", "original", "both"]
JobKind = Literal["evolve", "test"]
JobStatus = Literal["queued", "running", "finished", "failed", "cancelled"]


class EvolveRequest(BaseModel):
    fly: FlyDTO
    dials: Dials = "tuned"                    # which knobs evolution starts from: the fly's own, or the hand-set originals
    level: str = "1-1"
    generations: int = Field(default=15, ge=1, le=200)
    start: str = "level_start"                # "level_start", or a saved moment id to train from
    workers: Optional[int] = Field(default=None, ge=0, le=32)     # None = what this machine has; 0 = in the job's own process
    population: int = Field(default=12, ge=4, le=64)
    seed: int = 1
    train_n: int = Field(default=0, ge=0)     # 0 = every training episode; N = a small training set (smoke runs)
    flag_x: Optional[float] = None            # the level's flag x, for a level no run has reached it on yet


class TestJobRequest(BaseModel):
    fly: FlyDTO
    dials: TestDials = "both"                 # "both" tests the original and the tuned fly, for the Original vs Tuned summary
    level: str = "1-1"
    workers: Optional[int] = Field(default=None, ge=0, le=32)


class StartResult(BaseModel):
    """One dev-set start: how the fly did from it."""
    label: str                                # "start 3": which of the set's starts (no noise values shown)
    outcome: Literal["flag", "died", "stuck", "timeout"]
    max_x: float
    score: float
    jumps: int
    back_ups: int
    blocks: int
    mushroom: bool
    death: Optional[DeathDTO] = None


class DevSetResult(BaseModel):
    flags: int
    n: int
    mean_max_x: float
    min_max_x: float
    mean_score: float
    episodes: list[StartResult] = []


class KnobChange(BaseModel):
    """What evolution did to one knob, in words ("a bit toward strong"); never a number."""
    key: str
    label: str
    owner: str = ""                           # the sense or action the knob belongs to ("Looming", "Jump")
    lo_label: str
    hi_label: str
    words: str
    direction: Literal["same", "lo", "hi"]


class Generation(BaseModel):
    gen: int
    best: float                               # fitness of the generation's best fly, and of the generation's average
    mean: float
    best_ever: float


class JobProgress(BaseModel):
    phase: str = ""                           # training | dev set | testing | done
    generation: int = 0                       # generations finished
    generations: int = 0
    done: int = 0                             # test: episodes finished
    total: int = 0
    best: Optional[float] = None
    mean: Optional[float] = None
    eta_s: Optional[int] = None
    elapsed_s: int = 0
    bars: list[Generation] = []               # evolve: one per finished generation


class JobSummary(BaseModel):
    id: str
    kind: JobKind
    status: JobStatus
    fly: str
    level_id: str
    dials: TestDials
    created: float
    title: str                                # "Evolution of champion_e1s on 1-1" / "Test of champion_e1s on 1-1"
    headline: str = ""                        # a finished job's result: "Original 8/10 · Tuned 10/10", "10/10 on unseen starts"
    progress: JobProgress = JobProgress()


class JobDetail(JobSummary):
    error: str = ""
    generations: int = 0
    start: str = "level_start"
    results: dict[str, DevSetResult] = {}     # test: "original" and / or "tuned"
    changes: list[KnobChange] = []            # evolve: what evolution changed, in words
    dev_best: Optional[DevSetResult] = None   # evolve: the dev set on the best fly ...
    dev_start: Optional[DevSetResult] = None  # ... and on the fly it started from
    best_generation: Optional[int] = None
    saved_as: Optional[str] = None            # the fly yaml made by "Save as fly"


class UseFly(BaseModel):
    name: str = ""                            # "" = the evolved fly's own name


class JobCreated(BaseModel):
    id: str


# ---- video exports (clips for editing; each is a background job in $FLY_MARIO_DATA/videos/<id>/) ---------------------
VideoExport = Literal["run", "montage"]


class VideoRequest(BaseModel):
    """Asks for an export: it renders in the background and the mp4 is ready when the status says finished."""
    export: VideoExport
    show_senses: bool = True
    show_brain: bool = True
    run_id: str = ""                          # run: the saved run
    job_id: str = ""                          # montage: the evolution
    speed: Literal[1, 2, 4] = 2               # montage: playback speed (a run video is always 1x)


class VideoCheck(BaseModel):
    """What a replay did against what was recorded; hash_ok is None when nothing was recorded to compare with."""
    label: str
    outcome: str
    max_x: float
    hash_ok: Optional[bool] = None


class VideoProgress(BaseModel):
    phase: str = ""                           # rendering
    done: int = 0
    total: int = 0
    eta_s: Optional[int] = None
    elapsed_s: int = 0


class VideoSummary(BaseModel):
    id: str
    export: VideoExport
    of: str                                   # the run id (run) or the evolution's job id (montage) it shows
    title: str
    status: JobStatus
    created: float
    progress: VideoProgress = VideoProgress()
    video: Optional[str] = None               # URL of the mp4, once rendered
    error: str = ""
    duration_s: Optional[float] = None
    size_mb: Optional[float] = None
    render_s: Optional[float] = None
    speed: Optional[int] = None               # montage: the playback speed it was made at
    clips: Optional[int] = None               # montage: how many clips it has (one per generation)
    checks: list[VideoCheck] = []
