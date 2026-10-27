import { useEffect, useState, type ReactNode } from 'react'
import { api } from './api/client'
import type { Dials, Fly, Scene } from './api/models'
import { Ctx, defaultScene, emptyFly, nothingPicked, type Picked } from './draft'
import { FEATURES, LITE_PRESETS } from './features'

/** Scene and fly being edited, shared by the screens of one session. */
export function DraftProvider({ children }: { children: ReactNode }) {
  const [scene, setScene] = useState<Scene>(defaultScene)
  const [picked, setPicked] = useState<Picked>(nothingPicked)
  const [fly, setFly] = useState<Fly>(emptyFly)
  const [dials, setDials] = useState<Dials>('tuned')
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  // The lite build starts from the server's blank fly (its actions on, nothing attached): the only fly it offers.
  useEffect(() => { if (FEATURES.lite) api.getFly(LITE_PRESETS[0]).then(setFly).catch(() => {}) }, [])
  return <Ctx.Provider value={{ scene, setScene, picked, setPicked, fly, setFly, dials, setDials, lastRunId, setLastRunId }}>{children}</Ctx.Provider>
}

