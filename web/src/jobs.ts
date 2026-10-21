import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import type { JobDetail, VideoSummary } from './api/models'

const LIVE = new Set(['queued', 'running'])
export const isLive = (status: string | undefined) => !!status && LIVE.has(status)

/** A job, refreshed every two seconds while it is queued or running. */
export function useJob(id: string | null | undefined) {
  return useQuery<JobDetail>({
    queryKey: ['job', id], queryFn: () => api.getJob(id!), enabled: !!id, staleTime: 0,
    refetchInterval: (q) => (isLive(q.state.data?.status) || !q.state.data ? 2000 : false),
  })
}

/** "about 2 min left": time in words, to the nearest sensible step. */
export function eta(seconds: number | null | undefined): string {
  if (seconds == null) return 'working out how long it will take…'
  if (seconds < 10) return 'almost done'
  if (seconds < 90) return `about ${Math.round(seconds / 10) * 10} s left`
  if (seconds < 5400) return `about ${Math.round(seconds / 60)} min left`
  return `about ${Math.round(seconds / 360) / 10} h left`
}

/** A video export, refreshed every 1.5 s while it is queued or running. */
export function useVideo(id: string | null | undefined) {
  return useQuery<VideoSummary>({
    queryKey: ['video', id], queryFn: () => api.getVideo(id!), enabled: !!id, staleTime: 0,
    refetchInterval: (q) => (isLive(q.state.data?.status) || !q.state.data ? 1500 : false),
  })
}
