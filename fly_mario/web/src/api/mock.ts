// Fake data behind the Api interface. Every sense/object/action NAME lives only here;
// components render whatever the registry says.
import type { Api } from './client'
import type {
  FlyConfig, FrameEvent, KnobSpec, LevelInfo, MomentDetail, MomentSummary, ObjectInstance,
  Registry, RunEvent, RunRequest, RunResult, RunStream, Scene,
} from './types'

const knob = (key: string, label: string, lo_label: string, hi_label: string,
  origin: KnobSpec['origin'] = 'invented', def = 0.5): KnobSpec => ({
  key, label, lo_label, hi_label, default: def, lo: 0, hi: 1, scale: 'linear',
  origin, evolvable: true, floor: null,
})

const registry: Registry = {
  objects: [
    { name: 'goomba', label: 'Goomba', note: 'Walks toward Mario.', kind: 'enemy', default_loom_shape: 'body' },
    { name: 'koopa', label: 'Koopa', note: 'Shelled walker.', kind: 'enemy', default_loom_shape: 'body' },
    { name: 'pipe', label: 'Pipe', note: 'Solid green tube.', kind: 'obstacle', default_loom_shape: 'face' },
    { name: 'pit', label: 'Pit', note: 'A gap in the ground.', kind: 'terrain', default_loom_shape: 'edge' },
    { name: 'coin', label: 'Coin', note: 'Shiny pickup.', kind: 'pickup', default_loom_shape: 'body' },
  ],
  senses: [
    { name: 'looming', label: 'Looming', effect: 'Things that grow fast feel dangerous.', scope: 'per_object',
      colour: '#F83800', line: 'solid', feeds: ['LC4', 'LPLC2'],
      knobs: [knob('looming.reach', 'Reach', 'Near only', 'Far away', 'fly'), knob('looming.gain', 'Gain', 'Calm', 'Jumpy', 'invented')] },
    { name: 'sour', label: 'Sour', effect: 'Smells bad: push away.', scope: 'per_object',
      colour: '#F8D800', line: 'dotted', feeds: ['ORN-sour'],
      knobs: [knob('sour.range', 'Range', 'Close', 'Wide', 'fly')] },
    { name: 'sweet', label: 'Sweet', effect: 'Smells good: approach.', scope: 'per_object',
      colour: '#80D010', line: 'dotted', feeds: ['ORN-sweet'],
      knobs: [knob('sweet.strength', 'Strength', 'Faint', 'Strong', 'invented')] },
    { name: 'hum', label: 'Hum', effect: 'Background wing-beat rhythm.', scope: 'whole_fly',
      colour: '#80D010', line: 'dashed', feeds: ['JO'],
      knobs: [knob('hum.level', 'Hum', 'Quiet', 'Loud', 'invented')] },
    { name: 'home', label: 'Home', effect: 'A pull toward the flag.', scope: 'whole_fly',
      colour: '#FFFFFF', line: 'solid', feeds: ['CX'],
      knobs: [knob('home.pull', 'Pull', 'Wander', 'Beeline', 'fly')] },
  ],
  actions: [
    { name: 'jump', label: 'Jump', button: 'A', source_groups: ['GF', 'TTMn'], priority: 2, status: 'ready',
      knobs: [knob('jump.commit', 'Commit', 'Hesitant', 'Decisive', 'fly')] },
    { name: 'run', label: 'Run', button: 'B', source_groups: ['DNa'], priority: 1, status: 'soon', knobs: [] },
  ],
  scene_modifiers: [
    { name: 'remove_enemies', label: 'No enemies', description: 'Remove every enemy.', per_object: false },
    { name: 'keep_only', label: '{object} only', description: 'Keep only one kind of object.', per_object: true },
  ],
  presets: ['blank', 'jumpy-goomba', 'cautious'],
}

const kinds = ['overworld', 'underground', 'water', 'castle']
const levels: LevelInfo[] = [
  ...Array.from({ length: 32 }, (_, i) => {
    const w = Math.floor(i / 4) + 1, s = (i % 4) + 1
    return {
      id: `${w}-${s}`, label: `${w}-${s}`, kind: kinds[(s + w) % 4],
      status: (i === 0 ? 'cleared' : i < 12 ? 'open' : 'locked') as LevelInfo['status'],
      width: 3168,
      objects: i % 3 === 0 ? ['goomba', 'pipe', 'pit', 'coin'] : ['goomba', 'koopa', 'pipe', 'pit'],
    }
  }),
  ...[1, 2, 3].map((n): LevelInfo => ({
    id: `T-${n}`, label: `T-${n}`, kind: 'test', status: 'open', width: 1024, objects: ['goomba', 'pipe'],
  })),
]

const flies: Record<string, FlyConfig> = {
  blank: { name: 'blank', attachments: {}, loom_shapes: {}, whole_fly: [], actions: ['jump'], knobs: {}, provenance: {} },
  'jumpy-goomba': {
    name: 'jumpy-goomba', attachments: { looming: ['goomba', 'koopa'] }, loom_shapes: {},
    whole_fly: ['home'], actions: ['jump'], knobs: { 'looming.gain': 0.7 }, provenance: {},
  },
  cautious: {
    name: 'cautious', attachments: { looming: ['goomba', 'pipe'], sour: ['pit'] }, loom_shapes: {},
    whole_fly: ['home', 'hum'], actions: ['jump'], knobs: { 'looming.gain': 0.35 }, provenance: {},
  },
}

const baseScene: Scene = {
  level_id: '1-1', rom: 'v0', modifiers: [], start: 'level_start', noop: 0, sigma: 0, seed: 0,
  max_frames: 6000, stuck_frames: 300,
}

const moments: MomentSummary[] = [{
  id: 'm-demo', run_id: 'r-demo', name: 'Before the first Goomba', frame: 240, x: 420,
  auto: false, scene: baseScene, fly: flies['jumpy-goomba'],
}]
const runs = new Map<string, { req: RunRequest; fromMoment: string | null }>()
const tries: RunResult[] = []
let counter = 1

const TOTAL = 480
const DEATH_FRAME = 420
const delay = <T,>(v: T, ms = 120) => new Promise<T>((r) => setTimeout(() => r(v), ms))

function objectsAt(frame: number): ObjectInstance[] {
  const gx = 260 - frame * 0.6
  return [
    { type: 'goomba', id: 1, box: { x: gx, y: 192, w: 16, h: 16 }, side: 'ahead', state: {} },
    { type: 'pipe', id: 2, box: { x: 330 - frame * 0.1, y: 160, w: 32, h: 48 }, side: 'ahead', state: {} },
  ]
}

function frameEvent(frame: number): FrameEvent {
  const objs = objectsAt(frame)
  const g = objs[0].box
  const mario = { x: 60, y: frame > 300 && frame < 360 ? 150 : 192, w: 14, h: 16 }
  const near = Math.max(0, 1 - Math.abs(g.x - mario.x) / 200)
  return {
    type: 'frame', frame, total: TOTAL, mario, objects: objs,
    overlay: [
      { kind: 'box', geometry: [g.x, g.y, g.w, g.h], colour: '#F83800', line: 'solid' },
      { kind: 'line', geometry: [mario.x + 7, mario.y + 8, objs[1].box.x, objs[1].box.y + 10], colour: '#F8D800', line: 'dotted' },
      { kind: 'dot', geometry: [mario.x + 7, mario.y - 6, 3], colour: '#FFFFFF', line: 'solid' },
    ],
    rates: Object.fromEntries(
      ['LC4', 'LPLC2', 'GF', 'TTMn', 'ORN-sour', 'JO', 'CX', 'DNa'].map((n, i) =>
        [n, Math.min(1, Math.max(0, near * (1 - i * 0.08) + 0.08 * Math.sin(frame / (6 + i))))]),
    ),
  }
}

function makeResult(runId: string, req: RunRequest, parent: string | null, flag: boolean): RunResult {
  return {
    id: runId, fly: req.fly.name, scene: req.scene, parent_moment: parent,
    outcome: flag ? 'flag' : 'died',
    death: flag ? null : { cause: 'Touched a Goomba', frame: DEATH_FRAME, x: 760 },
    max_x: flag ? 3168 : 760, score: flag ? 4200 : 300, blocks: 2, mushroom: false,
    counts: { jumps: 7 }, moments: [], hash: 'mock' + runId,
  }
}

function runStream(runId: string): RunStream {
  const info = runs.get(runId)
  let cb: (e: RunEvent) => void = () => {}
  let frame = 0, playing = true, speed = 1, timer: ReturnType<typeof setInterval> | undefined, ended = false
  // better fly (more looming gain) clears the level in the mock; others die at the Goomba
  const flag = (info?.req.fly.knobs['looming.gain'] ?? 0) >= 0.6
  const emit = () => {
    if (ended) return
    cb(frameEvent(frame))
    if (frame === 200 && !runId.startsWith('r-resumed')) {
      cb({ type: 'moment', moment: { ...moments[0], id: 'auto-' + runId, name: 'Auto checkpoint', frame, auto: true } })
    }
    const last = flag ? TOTAL : DEATH_FRAME
    if (frame >= last) {
      ended = true
      if (info) cb({ type: 'end', result: makeResult(runId, info.req, info.fromMoment, flag) })
      else cb({ type: 'end', result: makeResult(runId, { fly: flies.blank, scene: baseScene, from_moment: null }, null, false) })
      return
    }
    frame += 1
  }
  const tick = () => { if (playing) emit() }
  const restartTimer = () => {
    if (timer) clearInterval(timer)
    timer = setInterval(() => { for (let i = 0; i < Math.max(1, Math.round(speed)); i++) tick() }, 1000 / 60 / Math.min(1, speed))
  }
  restartTimer()
  return {
    onEvent: (c) => { cb = c },
    play: () => { playing = true },
    pause: () => { playing = false },
    step: () => { playing = false; emit() },
    setSpeed: (m) => { speed = m; restartTimer() },
    restart: () => { frame = 0; ended = false; playing = true },
    close: () => { if (timer) clearInterval(timer) },
  }
}

export const mockApi: Api = {
  getRegistry: () => delay(registry),
  getLevels: () => delay(levels),
  getFly: (name) => delay(structuredClone(flies[name] ?? flies.blank)),
  saveFly: (fly) => { flies[fly.name] = structuredClone(fly); if (!registry.presets.includes(fly.name)) registry.presets.push(fly.name); return delay(fly) },
  startRun: (req) => {
    const id = `r-${counter++}`
    runs.set(id, { req, fromMoment: null })
    return delay({ run_id: id })
  },
  runStream,
  saveMoment: (runId, frame, name, auto = false) => {
    const info = runs.get(runId)
    const m: MomentSummary = {
      id: `m-${counter++}`, run_id: runId, name, frame, x: frame * 3, auto,
      scene: info?.req.scene ?? baseScene, fly: info?.req.fly ?? flies.blank,
    }
    moments.push(m)
    return delay(m)
  },
  getMoments: () => delay([...moments]),
  getMoment: (id): Promise<MomentDetail> => {
    const m = moments.find((x) => x.id === id) ?? moments[0]
    const objs = objectsAt(Math.min(m.frame, TOTAL))
    return delay({ ...m, objects: objs, on_screen: [...new Set(objs.map((o) => o.type))] })
  },
  getTries: (momentId) => delay(tries.filter((t) => t.parent_moment === momentId)),
  resumeFromMoment: (momentId, fly) => {
    const m = moments.find((x) => x.id === momentId) ?? moments[0]
    const id = `r-resumed-${counter++}`
    const req: RunRequest = { fly, scene: { ...m.scene, start: momentId }, from_moment: momentId }
    runs.set(id, { req, fromMoment: momentId })
    tries.push(makeResult(id, req, momentId, (fly.knobs['looming.gain'] ?? 0) >= 0.6))
    return delay({ run_id: id })
  },
}
