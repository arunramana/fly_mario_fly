import { createContext, useContext } from 'react'
import type { Dials, Fly, OverlayItem, RunRequest, Scene } from './api/models'

export const emptyFly: Fly = {
  name: 'blank', attachments: {}, loom_shapes: {}, whole_fly: [], actions: [], knobs: {}, provenance: {},
}
export const defaultScene: Scene = {
  level_id: '1-1', rom: 'v0', modifiers: [], start: 'level_start', noop: 0, sigma: 0, seed: 0,
  max_frames: 6000, stuck_frames: 300,
}

/** What the user has actually chosen on the Scene page: the defaults in `defaultScene` do not count until clicked. */
export interface Picked { level: boolean; test: boolean; start: boolean }
export const nothingPicked: Picked = { level: false, test: false, start: false }
export const everythingPicked: Picked = { level: true, test: true, start: true }

export interface Draft {
  scene: Scene
  setScene: (s: Scene) => void
  picked: Picked
  setPicked: (p: Picked) => void
  fly: Fly
  setFly: (f: Fly) => void
  /** Which dials the next run uses: the fly's tuned knobs, or every knob at its hand-set original. */
  dials: Dials
  setDials: (d: Dials) => void
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
 *  PNG, 256 x 240) and the senses overlay items (level pixels) with the screen's scroll. */
export interface Picture { game: string; overlay?: readonly OverlayItem[] | null; scrollX?: number }
export const momentPictures = new Map<string, Picture>()
const MAX_PICTURES = 40   // the newest moments only: a picture is ~100-300 kB, and auto moments arrive every 2 s
const MAX_REQUESTS = 30

/** Set a key, newest last, and drop the oldest entries beyond `cap`. */
export function setCapped<V>(map: Map<string, V>, key: string, value: V, cap: number): void {
  map.delete(key)
  map.set(key, value)
  while (map.size > cap) map.delete(map.keys().next().value as string)
}
export const rememberPicture = (id: string, p: Picture) => setCapped(momentPictures, id, p, MAX_PICTURES)

/** The request each run of this session was started with, and which try of that fly on that level it is. */
export const runRequests = new Map<string, { req: RunRequest; tryNo: number }>()
export function registerRun(runId: string, req: RunRequest): void {
  const same = [...runRequests.values()].filter((r) => r.req.fly.name === req.fly.name && r.req.scene.level_id === req.scene.level_id)
  setCapped(runRequests, runId, { req, tryNo: same.length + 1 }, MAX_REQUESTS)
}

/** Scenes saved by hand ("Save scene"), kept in this browser. */
export interface SavedScene { name: string; scene: Scene }
const SCENES_KEY = 'fly_mario_fly.scenes'
export function loadScenes(): SavedScene[] {
  try { return JSON.parse(localStorage.getItem(SCENES_KEY) ?? '[]') as SavedScene[] } catch { return [] }
}
export function saveScene(item: SavedScene): void {
  try {
    localStorage.setItem(SCENES_KEY, JSON.stringify([...loadScenes().filter((s) => s.name !== item.name), item]))
  } catch { /* storage blocked: the scene just is not remembered */ }
}
