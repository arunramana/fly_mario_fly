// Hand-written mirror of fly_mario/src/fly_mario/contracts.py (to be generated from OpenAPI later).
// Python sets/frozensets/tuples become arrays on the wire; dicts of sets become Record<string, string[]>.

export interface Box { x: number; y: number; w: number; h: number }

export type ObjectKind = 'enemy' | 'obstacle' | 'pickup' | 'terrain'
export type Side = 'ahead' | 'behind' | 'above' | 'below'
export type LineStyle = 'solid' | 'dotted' | 'dashed'

export interface ObjectInstance {
  type: string
  id: number
  box: Box
  side: Side
  state: Record<string, unknown>
}

/** Registry description of an ObjectType plug-in. */
export interface ObjectInfo {
  name: string
  label: string
  note: string
  kind: ObjectKind
  default_loom_shape: string
}

export interface KnobSpec {
  key: string
  label: string
  lo_label: string
  hi_label: string
  default: number
  lo: number
  hi: number
  scale: 'linear' | 'log'
  origin: 'fly' | 'invented'
  evolvable: boolean
  floor: number | null
}

/** Registry description of a Sense plug-in. */
export interface SenseInfo {
  name: string
  label: string
  effect: string
  scope: 'per_object' | 'whole_fly'
  colour: string
  line: LineStyle
  feeds: string[]
  knobs: KnobSpec[]
}

/** Registry description of an Action plug-in. `status` is a UI extra (not in contracts.py). */
export interface ActionInfo {
  name: string
  label: string
  button: string
  source_groups: string[]
  knobs: KnobSpec[]
  priority: number
  status: 'ready' | 'soon'
}

/** Registry description of a SceneModifier plug-in. `per_object` is a UI extra. */
export interface SceneModifierInfo {
  name: string
  label: string
  description: string
  per_object: boolean
}

export interface Registry {
  objects: ObjectInfo[]
  senses: SenseInfo[]
  actions: ActionInfo[]
  scene_modifiers: SceneModifierInfo[]
  presets: string[]
}

export interface OverlayItem {
  kind: 'box' | 'line' | 'dot' | 'wedge'
  geometry: number[]
  colour: string
  line: LineStyle
}

export interface Scene {
  level_id: string
  rom: string
  modifiers: [string, Record<string, unknown>][]
  start: 'level_start' | number | string
  noop: number
  sigma: number
  seed: number
  max_frames: number
  stuck_frames: number
}

export interface FlyConfig {
  name: string
  attachments: Record<string, string[]> // sense name -> object type names
  loom_shapes: Record<string, string>
  whole_fly: string[]
  actions: string[]
  knobs: Record<string, number>
  provenance: Record<string, unknown>
}

/** UI-side row for the level grid (not in contracts.py). */
export interface LevelInfo {
  id: string
  label: string
  kind: string
  status: 'open' | 'cleared' | 'locked'
  width: number
  objects: string[] // object type names present in this level
}

/** SavedMoment without the binary state. */
export interface MomentSummary {
  id: string
  run_id: string
  name: string
  frame: number
  x: number
  auto: boolean
  scene: Scene
  fly: FlyConfig
}

export interface MomentDetail extends MomentSummary {
  on_screen: string[] // object type names visible at this moment
  objects: ObjectInstance[]
}

export interface RunResult {
  id: string
  fly: string
  scene: Scene
  parent_moment: string | null
  outcome: 'flag' | 'died' | 'stuck' | 'timeout'
  death: { cause?: string; frame?: number; x?: number } | null
  max_x: number
  score: number
  blocks: number
  mushroom: boolean
  counts: Record<string, number>
  moments: string[]
  hash: string
}

export interface RunRequest {
  fly: FlyConfig
  scene: Scene
  from_moment: string | null
}

/** One streamed frame. rates: neuron group name -> 0..1. */
export interface FrameEvent {
  type: 'frame'
  frame: number
  total: number
  mario: Box
  objects: ObjectInstance[]
  overlay: OverlayItem[]
  rates: Record<string, number>
}
export interface MomentEvent { type: 'moment'; moment: MomentSummary }
export interface EndEvent { type: 'end'; result: RunResult }
export type RunEvent = FrameEvent | MomentEvent | EndEvent

export interface RunStream {
  onEvent(cb: (e: RunEvent) => void): void
  play(): void
  pause(): void
  step(): void
  setSpeed(multiplier: number): void
  restart(): void
  close(): void
}
