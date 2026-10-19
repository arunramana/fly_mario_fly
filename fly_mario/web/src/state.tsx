import { createContext, useContext, useState, type ReactNode } from 'react'
import type { FlyConfig, Scene } from './api/types'

export const emptyFly: FlyConfig = {
  name: 'blank', attachments: {}, loom_shapes: {}, whole_fly: [], actions: ['jump'], knobs: {}, provenance: {},
}
export const defaultScene: Scene = {
  level_id: '1-1', rom: 'v0', modifiers: [], start: 'level_start', noop: 0, sigma: 0, seed: 0,
  max_frames: 6000, stuck_frames: 300,
}

interface Draft {
  scene: Scene
  setScene: (s: Scene) => void
  fly: FlyConfig
  setFly: (f: FlyConfig) => void
  lastRunId: string | null
  setLastRunId: (id: string) => void
}
const Ctx = createContext<Draft | null>(null)

/** Scene and fly being edited, shared by the screens of one session. */
export function DraftProvider({ children }: { children: ReactNode }) {
  const [scene, setScene] = useState<Scene>(defaultScene)
  const [fly, setFly] = useState<FlyConfig>(emptyFly)
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  return <Ctx.Provider value={{ scene, setScene, fly, setFly, lastRunId, setLastRunId }}>{children}</Ctx.Provider>
}

export function useDraft(): Draft {
  const v = useContext(Ctx)
  if (!v) throw new Error('DraftProvider missing')
  return v
}
