import { useState, type ReactNode } from 'react'
import type { Fly, Scene } from './api/models'
import { Ctx, defaultScene, emptyFly } from './draft'

/** Scene and fly being edited, shared by the screens of one session. */
export function DraftProvider({ children }: { children: ReactNode }) {
  const [scene, setScene] = useState<Scene>(defaultScene)
  const [fly, setFly] = useState<Fly>(emptyFly)
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  return <Ctx.Provider value={{ scene, setScene, fly, setFly, lastRunId, setLastRunId }}>{children}</Ctx.Provider>
}

