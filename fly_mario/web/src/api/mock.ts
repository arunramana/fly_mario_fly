// Offline stand-in for the API (VITE_MOCK=1), same shapes as the generated schema. Every sense/object/action
// NAME lives only here; components render whatever the registry says.
import type { Api } from './client'
import type {
  Fly, FrameEvent, KnobUI, LevelInfo, MomentSummary, Registry, RunEvent, RunRequest, RunResult, RunStream,
  Scene, Try,
} from './models'

const knob = (key: string, label: string, lo_label: string, hi_label: string,
  origin: KnobUI['origin'] = 'invented'): KnobUI => ({
  key, label, lo_label, hi_label, position: 0.5, scale: 'linear', origin, evolvable: true, floor_position: null, kind: 'slider',
})

const registry: Registry = {
  objects: [
    { name: 'goomba', label: 'Goomba', note: 'Walks toward Mario.', kind: 'enemy', default_loom_shape: 'body' },
    { name: 'koopa', label: 'Koopa', note: 'Shelled walker.', kind: 'enemy', default_loom_shape: 'body' },
    { name: 'pipe', label: 'Pipe', note: 'Solid green tube.', kind: 'obstacle', default_loom_shape: 'face' },
    { name: 'pit', label: 'Pit', note: 'A gap in the ground.', kind: 'terrain', default_loom_shape: 'edge' },
  ],
  senses: [
    { name: 'looming', label: 'Looming', effect: 'Things that grow fast feel dangerous.', scope: 'per_object',
      colour: '#F83800', line: 'solid', feeds: ['LC4', 'LPLC2'], order: 10,
      knobs: [knob('loom.eyes', 'Eyes used', 'right eye only', 'both eyes', 'fly')] },
    { name: 'sour_smell', label: 'Sour smell', effect: 'An enemy smells of acid.', scope: 'per_object',
      colour: '#F8D800', line: 'dotted', feeds: ['ORN'], order: 20,
      knobs: [knob('sour_smell.gain', 'Sourness', 'faint', 'strong', 'invented')] },
    { name: 'home', label: 'Home', effect: 'Keep going right.', scope: 'whole_fly',
      colour: '#FFFFFF', line: 'solid', feeds: ['LC10a'], order: 60,
      knobs: [knob('home.drive', 'Pull to the right', 'weak', 'strong', 'fly')] },
  ],
  shapes: [],
  actions: [
    { name: 'jump', label: 'Jump', button: 'A', source_groups: ['GF'], priority: 2, order: 0, status: 'ready', knobs: [] },
    { name: 'walk', label: 'Walk', button: 'right', source_groups: ['DNa'], priority: 1, order: 1, status: 'soon', knobs: [] },
  ],
  scene_modifiers: [
    { name: 'whole_level', label: 'Whole level', description: '', params: [], per_object: false },
    { name: 'no_enemies', label: 'No enemies', description: '', params: [], per_object: false },
    { name: 'keep_only', label: 'Keep only', description: '', per_object: true,
      params: [{ key: 'types', label: 'Object types to keep', type: 'object_types', default: [] }] },
  ],
  test_scenes: [],
  presets: ['blank', 'jumpy'],
}

const levels: LevelInfo[] = [
  { id: '1-1', label: '1-1', kind: 'overground', status: 'cleared', status_text: 'won 1/1', scanned: true, partial: false, width: 3168, objects: ['goomba', 'pipe', 'pit'] },
  { id: '1-2', label: '1-2', kind: 'underground', status: 'open', status_text: 'not tried', scanned: false, partial: false, width: null, objects: null },
]

const flies: Record<string, Fly> = {
  blank: { name: 'blank', attachments: {}, loom_shapes: {}, whole_fly: [], actions: ['jump'], knobs: {}, provenance: {} },
  jumpy: { name: 'jumpy', attachments: { looming: ['goomba'], sour_smell: ['goomba'] }, loom_shapes: {}, whole_fly: ['home'], actions: ['jump'], knobs: {}, provenance: {} },
}

const baseScene: Scene = {
  level_id: '1-1', rom: 'v0', modifiers: [], start: 'level_start', noop: 0, sigma: 0, seed: 0,
  max_frames: 6000, stuck_frames: 300,
}

const moments: MomentSummary[] = []
const runs = new Map<string, { req: RunRequest }>()
const tries: (Try & { moment: string })[] = []
let counter = 1

const DEATH_FRAME = 420
const delay = <T,>(v: T, ms = 100) => new Promise<T>((r) => setTimeout(() => r(v), ms))

function picture(frame: number): string {
  const c = document.createElement('canvas')
  c.width = 256; c.height = 240
  const g = c.getContext('2d')!
  g.fillStyle = '#5c94fc'; g.fillRect(0, 0, 256, 240)
  g.fillStyle = '#b84c00'; g.fillRect(0, 208, 256, 32)
  g.fillStyle = '#a0522d'; g.fillRect(260 - frame * 0.6, 192, 16, 16)
  g.fillStyle = '#f83800'; g.fillRect(60, 192, 14, 16)
  return c.toDataURL('image/png').split(',')[1]
}

function frameEvent(frame: number): FrameEvent {
  const gx = 260 - frame * 0.6
  const near = Math.max(0, 1 - Math.abs(gx - 60) / 200)
  return {
    type: 'frame', frame, total: 6000, frame_png: picture(frame), x: frame, buttons: [],
    mario: { x: 60, y: 160, w: 14, h: 16 }, scroll_x: 0, scroll_x_after: 0,
    objects: [{ type: 'goomba', id: 1, box: { x: gx, y: 160, w: 16, h: 16 }, side: 'ahead' }],
    overlay: [
      { kind: 'box', geometry: [gx, 160, 16, 16], colour: '#F83800', line: 'solid', anchor: 'level' },
      { kind: 'dot', geometry: [0, 152, 2.75], colour: '#FFFFFF', line: 'solid', anchor: 'screen_right' },
    ],
    rates: { LC4: near, LPLC2: near * 0.8, GF: near * near, TTMn: near * near * 0.9 },
    overlay_png: null, overlay_at: null, brain_jpg: null,
  }
}

function result(runId: string, req: RunRequest, parent: string | null | undefined, flag: boolean): RunResult {
  return {
    id: runId, fly: req.fly.name, scene: req.scene, parent_moment: parent ?? null,
    outcome: flag ? 'flag' : 'died', death: flag ? null : { kind: 'enemy', object_type: 'goomba', object_label: 'Goomba', x: 760 },
    max_x: flag ? 3168 : 760, score: 0, blocks: 0, mushroom: false, counts: {}, moments: [], hash: '', dials: req.dials ?? 'tuned',
  }
}

const strong = (fly: Fly) => (fly.knobs['sour_smell.gain'] ?? 0.5) > 0.7

function openRun(runId: string): RunStream {
  const req = runs.get(runId)!.req
  const flag = strong(req.fly)
  let cb: (e: RunEvent) => void = () => {}
  let frame = 0, playing = true, speed = 1
  let timer: ReturnType<typeof setInterval> | undefined
  const emit = () => {
    cb(frameEvent(frame))
    if (frame === DEATH_FRAME && !flag) {
      const m: MomentSummary = {
        id: `${runId}@${frame - 180}d`, run_id: runId, name: '3 s before death', frame: frame - 180, x: 600,
        auto: true, kind: 'death', scene: req.scene, fly: req.fly, on_screen: ['goomba'],
      }
      moments.push(m)
      cb({ type: 'moment', moment: m })
      cb({ type: 'end', result: result(runId, req, req.from_moment, false) })
      clearInterval(timer)
      return
    }
    if (frame === 600 && flag) {
      cb({ type: 'end', result: result(runId, req, req.from_moment, true) })
      clearInterval(timer)
      return
    }
    frame += 1
  }
  const arm = () => {
    clearInterval(timer)
    timer = setInterval(() => { if (playing) emit() }, 1000 / 60 / Math.min(4, Math.max(0.25, speed)))
  }
  arm()
  return {
    onEvent: (c) => { cb = c },
    play: () => { playing = true },
    pause: () => { playing = false },
    step: () => { playing = false; emit() },
    setSpeed: (m) => { speed = m; arm() },
    close: () => clearInterval(timer),
  }
}

export const mockApi: Api = {
  getRegistry: () => delay(registry),
  getLevels: () => delay(levels),
  getFly: (name) => delay(structuredClone(flies[name] ?? flies.blank)),
  saveFly: (fly) => {
    flies[fly.name] = structuredClone(fly)
    if (!registry.presets.includes(fly.name)) registry.presets.push(fly.name)
    return delay(fly)
  },
  startRun: (req) => {
    const id = `r-${counter++}`
    runs.set(id, { req })
    if (req.from_moment) tries.push({ moment: req.from_moment, run_id: id, change: 'sour smell stronger', outcome: strong(req.fly) ? 'flag' : 'died', max_x: strong(req.fly) ? 3168 : 760 })
    return delay({ run_id: id })
  },
  openRun,
  getRun: () => delay(null),
  saveMoment: (runId, name, frame) => {
    const req = runs.get(runId)?.req
    const m: MomentSummary = {
      id: `${runId}@${frame ?? 0}`, run_id: runId, name: name || 'Moment', frame: frame ?? 0, x: 0, auto: false,
      kind: 'manual', scene: req?.scene ?? baseScene, fly: req?.fly ?? flies.blank, on_screen: ['goomba'],
    }
    moments.push(m)
    return delay(m)
  },
  getRunMoments: (runId) => delay(moments.filter((m) => m.run_id === runId)),
  getRuns: () => delay([]),
  getMoment: (id) => delay(moments.find((m) => m.id === id) ?? moments[0]),
  getTries: (id) => delay(tries.filter((t) => t.moment === id)),
  getBrainMap: () => delay(''),
}
