import { api } from '../api/client'
import { eta, isLive, useJob } from '../jobs'

/** "Test this fly (10 starts)": progress while the 10 starts are played, then "Original 8/10 · Tuned 10/10". */
export default function TestResult({ jobId }: { jobId: string }) {
  const job = useJob(jobId)
  const d = job.data
  if (!d) return <p className="muted">Starting the test…</p>
  const p = d.progress
  return (
    <div data-testid="test-panel" data-status={d.status}>
      {isLive(d.status) && (
        <div className="job-progress">
          <div className="pbar" role="progressbar"><i style={{ width: `${p.total ? (p.done / p.total) * 100 : 3}%` }} /></div>
          <p>{p.phase === 'testing' ? `Played ${p.done} of ${p.total} runs` : 'Starting up…'} · {eta(p.eta_s)}</p>
          <button className="btn sm" onClick={() => api.cancelJob(d.id).then(() => job.refetch())}>Cancel</button>
        </div>
      )}
      {d.status === 'failed' && <p className="err" role="alert">The test failed: {d.error}</p>}
      {d.status === 'cancelled' && <p className="muted">Cancelled.</p>}
      {d.status === 'finished' && (
        <p>
          <b className="headline" data-testid="test-headline">{d.headline}</b>{' '}
          <span className="muted">reached the flag, from 10 starts the fly was never tuned on</span>
        </p>
      )}
    </div>
  )
}
