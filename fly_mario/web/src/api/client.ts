// The only module components import for data. `python -m fly_mario.api` serves it (default http://127.0.0.1:8000,
// override with VITE_API_URL); VITE_MOCK=1 swaps in the offline mock.
import type {
  Fly, LevelInfo, MomentSummary, Registry, RunEvent, RunRequest, RunResult, RunStream, RunSummary, Try,
} from './models'
import { mockApi } from './mock'

export interface Api {
  getRegistry(): Promise<Registry>
  getLevels(): Promise<LevelInfo[]>
  getFly(name: string): Promise<Fly>
  /** Creates the fly; with `replace`, an existing fly of that name is overwritten instead of refused. */
  saveFly(fly: Fly, replace?: boolean): Promise<Fly>
  startRun(req: RunRequest): Promise<{ run_id: string }>
  openRun(runId: string): RunStream
  getRun(runId: string): Promise<RunResult | null>
  /** frame: null = the moment is "now"; a number = one of the recent in-memory snapshots. */
  saveMoment(runId: string, name: string, frame?: number | null): Promise<MomentSummary>
  getRunMoments(runId: string): Promise<MomentSummary[]>
  getRuns(): Promise<RunSummary[]>
  getMoment(id: string): Promise<MomentSummary>
  getTries(momentId: string): Promise<Try[]>
}

const BASE: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

const enc = encodeURIComponent

function openRun(runId: string): RunStream {
  const ws = new WebSocket(`${BASE.replace(/^http/, 'ws')}/runs/${enc(runId)}/live`)
  let cb: (e: RunEvent) => void = () => {}
  const queued: string[] = []
  const send = (m: object) => {
    const s = JSON.stringify(m)
    if (ws.readyState === WebSocket.OPEN) ws.send(s); else queued.push(s)
  }
  ws.onopen = () => { for (const s of queued.splice(0)) ws.send(s) }
  ws.onmessage = (m) => cb(JSON.parse(m.data as string) as RunEvent)
  ws.onclose = (e) => {
    if (e.code === 4404) cb({ type: 'error', message: 'This run is not on the server (it may have restarted).' })
  }
  return {
    onEvent: (c) => { cb = c },
    play: () => send({ type: 'play' }),
    pause: () => send({ type: 'pause' }),
    step: () => send({ type: 'step' }),
    // 100 = as fast as the machine allows (the API treats 0 or >= 100 that way)
    setSpeed: (value) => send({ type: 'speed', value }),
    close: () => { cb = () => {}; ws.close() },
  }
}

const httpApi: Api = {
  getRegistry: () => call('GET', '/registry'),
  getLevels: () => call('GET', '/levels'),
  getFly: (name) => call('GET', `/flies/${enc(name)}`),
  saveFly: async (fly, replace = false) => {
    try {
      return await call<Fly>('POST', '/flies', fly)
    } catch (e) {
      if (replace && e instanceof ApiError && e.status === 409) return call<Fly>('PUT', `/flies/${enc(fly.name)}`, fly)
      throw e
    }
  },
  startRun: async (req) => ({ run_id: (await call<RunSummary>('POST', '/runs', req)).id }),
  openRun,
  getRun: async (runId) => (await call<{ result: RunResult | null }>('GET', `/runs/${enc(runId)}`)).result,
  saveMoment: (runId, name, frame = null) => call('POST', `/runs/${enc(runId)}/moments`, { name, frame }),
  getRunMoments: (runId) => call('GET', `/runs/${enc(runId)}/moments`),
  getRuns: () => call('GET', '/runs'),
  getMoment: (id) => call('GET', `/moments/${enc(id)}`),
  getTries: (momentId) => call('GET', `/moments/${enc(momentId)}/tries`),
}

export const api: Api = import.meta.env.VITE_MOCK === '1' ? mockApi : httpApi
