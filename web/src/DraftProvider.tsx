import { useState, type ReactNode } from 'react'
import type { Dials, Fly, Scene } from './api/models'
import { Ctx, defaultScene, emptyFly, nothingPicked, type Picked } from './draft'

/** Scene and fly being edited, shared by the screens of one session. */
export function DraftProvider({ children }: { children: ReactNode }) {
  const [scene, setScene] = useState<Scene>(defaultScene)
  const [picked, setPicked] = useState<Picked>(nothingPicked)
  const [fly, setFly] = useState<Fly>(emptyFly)
  const [dials, setDials] = useState<Dials>('tuned')
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  return <Ctx.Provider value={{ scene, setScene, picked, setPicked, fly, setFly, dials, setDials, lastRunId, setLastRunId }}>{children}</Ctx.Provider>
}

