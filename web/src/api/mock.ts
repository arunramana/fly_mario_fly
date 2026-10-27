// Offline stand-in for the API (VITE_MOCK=1), same shapes as the generated schema. Every sense/object/action
// NAME lives only here; components render whatever the registry says.
import type { Api } from './client'
import type {
  DevSetResult, EvolveRequest, Fly, FrameEvent, JobDetail, JobSummary, KnobUI, TestJobRequest, LevelInfo, MomentSummary, Registry, RunEvent, RunRequest, RunResult, RunStream,
  Scene, Try, VideoRequest, VideoSummary,
} from './models'

const knob = (key: string, label: string, lo_label: string, hi_label: string,
  origin: KnobUI['origin'] = 'invented'): KnobUI => ({
  key, label, lo_label, hi_label, position: 0.5, scale: 'linear', origin, evolvable: true, floor_position: null, kind: 'slider',
})

const registry: Registry = {
  objects: [
    { name: 'goomba', label: 'Goomba', note: 'Walks toward Mario.', kind: 'enemy', default_loom_shape: 'body', icon: '', order: 0 },
    { name: 'koopa', label: 'Koopa', note: 'Shelled walker.', kind: 'enemy', default_loom_shape: 'body', icon: '', order: 1 },
    { name: 'pipe', label: 'Pipe', note: 'Solid green tube.', kind: 'obstacle', default_loom_shape: 'face', icon: '', order: 7 },
    { name: 'pit', label: 'Pit', note: 'A gap in the ground.', kind: 'terrain', default_loom_shape: 'edge', icon: '', order: 9 },
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
  { id: '1-1', label: '1-1', kind: 'overground', status: 'cleared', status_text: 'won 1/1', scanned: true, partial: false, objects: ['goomba', 'pipe', 'pit'] },
  { id: '1-2', label: '1-2', kind: 'underground', status: 'open', status_text: 'not tried', scanned: false, partial: false, objects: null },
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
    brain_jpg: null,
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

// ---- jobs: an evolution takes 2 s a generation, a test 4 s; the numbers are made up for the offline look only
const dev = (flags: number): DevSetResult => ({
  flags, n: 10, mean_max_x: 2400, min_max_x: 1200, mean_score: 800,
  episodes: Array.from({ length: 10 }, (_, i) => ({
    label: `start ${i + 1}`, outcome: i < flags ? 'flag' : 'died', max_x: i < flags ? 3168 : 1200, score: 800, jumps: 30, back_ups: 5,
    blocks: 3, mushroom: i % 2 === 0, death: null,
  })),
})
interface MockJob { summary: JobSummary; fly: Fly; cancelled: boolean; t0: number; kind: 'evolve' | 'test'; gens: number; detail: () => JobDetail }
const jobs = new Map<string, MockJob>()
function startJob(kind: 'evolve' | 'test', req: EvolveRequest | TestJobRequest): Promise<string> {
  const id = `${kind}-${counter++}`
  const gens = kind === 'evolve' ? ((req as EvolveRequest).generations ?? 15) : 0
  const job: MockJob = {
    kind, gens, fly: req.fly, cancelled: false, t0: Date.now(),
    summary: { id, kind, status: 'running', fly: req.fly.name, level_id: req.level, dials: req.dials ?? 'tuned', created: Date.now() / 1000,
      title: `${kind === 'evolve' ? 'Evolution' : 'Test'} of ${req.fly.name} on ${req.level}`, headline: '', progress: {} as JobSummary['progress'] },
    detail: () => {
      const done = job.cancelled ? 'cancelled' : (Date.now() - job.t0) / (kind === 'evolve' ? 2000 * gens + 1000 : 4000) >= 1
      const g = Math.min(gens, Math.floor((Date.now() - job.t0) / 2000))
      const s: JobSummary = { ...job.summary, status: job.cancelled ? 'cancelled' : done ? 'finished' : 'running',
        headline: done === true ? (kind === 'test' ? 'Original 8/10 · Tuned 10/10' : '10/10 on unseen starts (was 8/10)') : '',
        progress: { phase: done === true ? 'done' : kind === 'test' ? 'testing' : 'training', generation: g, generations: gens, done: done === true ? 20 : 8, total: 20,
          eta_s: 5, elapsed_s: 3, best: 1, mean: 0.8, bars: Array.from({ length: g }, (_, i) => ({ gen: i, best: 0.6 + i * 0.05, mean: 0.4 + i * 0.03, best_ever: 0.6 + i * 0.05 })) } }
      return { ...s, error: '', generations: gens, start: 'level_start', results: (done === true && kind === 'test' ? { original: dev(8), tuned: dev(10) } : {}) as Record<string, DevSetResult>,
        changes: done === true && kind === 'evolve' ? [{ key: 'sour_smell.gain', label: 'Sourness', owner: 'Sour smell', lo_label: 'faint', hi_label: 'strong', words: 'a bit toward faint', direction: 'lo' }] : [],
        dev_best: done === true && kind === 'evolve' ? dev(10) : null, dev_start: done === true && kind === 'evolve' ? dev(8) : null, best_generation: gens - 1, saved_as: null }
    },
  }
  jobs.set(id, job)
  return delay(id)
}

// A video export in the mock: the mp4 is ready 3 s after the request.
interface MockVideo { req: VideoRequest; t0: number; cancelled: boolean }
const videos = new Map<string, MockVideo>()
function videoView(id: string): VideoSummary {
  const v = videos.get(id)!
  const done = Date.now() - v.t0 > 3000
  const status = v.cancelled ? 'cancelled' : done ? 'finished' : 'running'
  return { id, export: v.req.export, of: v.req.run_id || v.req.job_id || '', title: `Video (${v.req.export})`, status, created: v.t0 / 1000,
    progress: { phase: 'rendering', done: 1, total: 4, eta_s: 3, elapsed_s: 1 },
    video: status === 'finished' ? 'data:video/mp4;base64,' : null, error: '',
    duration_s: done ? 75 : null, size_mb: done ? 38 : null, render_s: done ? 60 : null, checks: [] }
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
  getLiteRun: (runId) => delay({ run_id: runId, status: 'failed', error: 'The offline mock has no lite server.' }),
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
  startEvolve: (req) => startJob('evolve', req),
  startTest: (req) => startJob('test', req),
  getJobs: () => delay([...jobs.values()].map((j) => j.summary)),
  getJob: (id) => delay(jobs.get(id)!.detail()),
  cancelJob: (id) => { jobs.get(id)!.cancelled = true; return delay(jobs.get(id)!.detail()) },
  useEvolvedFly: (id, name) => delay({ ...(jobs.get(id)?.fly ?? flies.blank), name: name || 'evolved' }),
  startVideo: (req) => {
    const id = `v-${counter++}`
    videos.set(id, { req, t0: Date.now(), cancelled: false })
    return delay(videoView(id))
  },
  getVideo: (id) => delay(videoView(id)),
  getVideos: () => delay([...videos.keys()].map(videoView)),
  cancelVideo: (id) => { videos.get(id)!.cancelled = true; return delay(videoView(id)) },
}
