import { createContext, useContext, useState, type ReactNode } from 'react'
import type { Fly, Scene } from './api/models'

export const emptyFly: Fly = {
  name: 'blank', attachments: {}, loom_shapes: {}, whole_fly: [], actions: [], knobs: {}, provenance: {},
}
export const defaultScene: Scene = {
  level_id: '1-1', rom: 'v0', modifiers: [['whole_level', {}]], start: 'level_start', noop: 0, sigma: 0, seed: 0,
  max_frames: 6000, stuck_frames: 300,
}

interface Draft {
  scene: Scene
  setScene: (s: Scene) => void
  fly: Fly
  setFly: (f: Fly) => void
  lastRunId: string | null
  setLastRunId: (id: string) => void
}
const Ctx = createContext<Draft | null>(null)

/** Scene and fly being edited, shared by the screens of one session. */
export function DraftProvider({ children }: { children: ReactNode }) {
  const [scene, setScene] = useState<Scene>(defaultScene)
  const [fly, setFly] = useState<Fly>(emptyFly)
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  return <Ctx.Provider value={{ scene, setScene, fly, setFly, lastRunId, setLastRunId }}>{children}</Ctx.Provider>
}

export function useDraft(): Draft {
  const v = useContext(Ctx)
  if (!v) throw new Error('DraftProvider missing')
  return v
}

/** The game picture at a saved moment (base64 PNG), kept by the run screen so the moment screen can show it. */
export const momentPictures = new Map<string, string>()
