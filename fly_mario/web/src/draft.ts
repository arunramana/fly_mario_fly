import { createContext, useContext } from 'react'
import type { Fly, RunRequest, Scene } from './api/models'

export const emptyFly: Fly = {
  name: 'blank', attachments: {}, loom_shapes: {}, whole_fly: [], actions: [], knobs: {}, provenance: {},
}
export const defaultScene: Scene = {
  level_id: '1-1', rom: 'v0', modifiers: [['whole_level', {}]], start: 'level_start', noop: 0, sigma: 0, seed: 0,
  max_frames: 6000, stuck_frames: 300,
}

export interface Draft {
  scene: Scene
  setScene: (s: Scene) => void
  fly: Fly
  setFly: (f: Fly) => void
  lastRunId: string | null
  setLastRunId: (id: string) => void
}
export const Ctx = createContext<Draft | null>(null)

export function useDraft(): Draft {
  const v = useContext(Ctx)
  if (!v) throw new Error('DraftProvider missing')
  return v
}

/** What the run screen showed at a frame, kept so the moment screen can show the same picture: the game screen (base64
 *  PNG, 256 x 240) and the transparent senses overlay (base64 PNG) with its [x, y] on the game at x4. */
export interface Picture { game: string; overlay?: string | null; at?: number[] | null }
export const momentPictures = new Map<string, Picture>()

/** The request each run of this session was started with, and which try of that fly on that level it is. */
export const runRequests = new Map<string, { req: RunRequest; tryNo: number }>()
export function registerRun(runId: string, req: RunRequest): void {
  const same = [...runRequests.values()].filter((r) => r.req.fly.name === req.fly.name && r.req.scene.level_id === req.scene.level_id)
  runRequests.set(runId, { req, tryNo: same.length + 1 })
}

/** Width and height of a base64 PNG, read from its header. */
export function pngSize(b64: string): [number, number] {
  const head = atob(b64.slice(0, 36))
  const at = (i: number) => (head.charCodeAt(i) << 24 | head.charCodeAt(i + 1) << 16 | head.charCodeAt(i + 2) << 8 | head.charCodeAt(i + 3)) >>> 0
  return [at(16), at(20)]
}

/** Scenes saved by hand ("Save scene"), kept in this browser. */
export interface SavedScene { name: string; scene: Scene }
const SCENES_KEY = 'fly_mario.scenes'
export function loadScenes(): SavedScene[] {
  try { return JSON.parse(localStorage.getItem(SCENES_KEY) ?? '[]') as SavedScene[] } catch { return [] }
}
export function saveScene(item: SavedScene): void {
  try {
    localStorage.setItem(SCENES_KEY, JSON.stringify([...loadScenes().filter((s) => s.name !== item.name), item]))
  } catch { /* storage blocked: the scene just is not remembered */ }
}
