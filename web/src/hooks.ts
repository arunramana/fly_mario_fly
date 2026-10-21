import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from './api/client'
import type { RunRequest } from './api/models'
import { registerRun, useDraft } from './draft'

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Start a run and go and watch it. The request is remembered so the run screen can restart it. */
export function useStartRun() {
  const nav = useNavigate()
  const { setLastRunId } = useDraft()
  return useMutation({
    mutationFn: async (req: RunRequest) => ({ ...(await api.startRun(req)), req }),
    onSuccess: ({ run_id, req }) => {
      registerRun(run_id, req)
      setLastRunId(run_id)
      nav(`/run/${run_id}`)
    },
  })
}
