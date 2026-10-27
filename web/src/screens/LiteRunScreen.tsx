import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api, videoUrl } from '../api/client'
import { runRequests } from '../draft'
import { errText } from '../hooks'

const OUTCOME: Record<string, string> = { flag: 'Reached the flag', died: 'Died', stuck: 'Got stuck', timeout: 'Ran out of time' }

/** The lite server's run: it plays the settings and answers with a video. This screen waits for it (queued, then running with a
 *  frame count) and plays the video. There is nothing to pause or save here: the run is already over when the video exists. */
export default function LiteRunScreen() {
  const { runId = '' } = useParams()
  const nav = useNavigate()
  const run = useQuery({
    queryKey: ['lite-run', runId],
    queryFn: () => api.getLiteRun(runId),
    refetchInterval: (q) => (q.state.data && ['done', 'failed'].includes(q.state.data.status) ? false : 1000),
    staleTime: 0,
  })
  const again = () => nav('/fly')
  if (run.isError) {
    return <div className="run"><p className="err" role="alert">{errText(run.error)}</p><button className="btn" onClick={again}>← Back to the fly</button></div>
  }
  const r = run.data
  if (!r) return <p>Loading…</p>
  const s = r.summary
  const res = s?.result
  const info = runRequests.get(runId)
  return (
    <div className="run lite-run">
      {r.status === 'failed' && <p className="err" role="alert">The run failed: {r.error}</p>}
      {(r.status === 'queued' || r.status === 'running') && (
        <section className="box" aria-live="polite">
          <h2 className="label">{r.status === 'queued' ? 'Waiting for a free slot' : 'The fly is playing'}</h2>
          {r.status === 'queued'
            ? <p>{r.position ? `${r.position} run${r.position === 1 ? '' : 's'} ahead of yours.` : 'Yours is next.'}</p>
            : <progress max={r.max_frames ?? 3600} value={r.frame ?? 0} aria-label="frames played" />}
          <p className="muted">A run takes about ten seconds. The same settings, played again, are shown at once.</p>
        </section>
      )}
      {r.status === 'done' && r.video_url && (
        <>
          <video src={videoUrl(r.video_url)} controls autoPlay muted loop playsInline preload="auto" style={{ width: '100%', maxWidth: 640, imageRendering: 'pixelated' }}
            aria-label="the run" />
          <p className="lead">
            {res ? `${OUTCOME[res.outcome] ?? res.outcome} · got as far as x ${Math.round(res.max_x)} · ${Math.round(Number(res.counts.frames ?? 0))} game frames` : ''}
            {info ? ` · ${info.req.fly.name}` : ''}
          </p>
          <p className="muted">
            The video is drawn at {s?.fps ?? 15} frames a second (the game ran at 60). Left: the fly&apos;s real neurons at their somas, lit by how active
            their group is, and the groups listed below. The boxes on the game are what its senses look at; the squares under it are the buttons it holds.
          </p>
        </>
      )}
      <div className="row" style={{ marginTop: 14 }}>
        <button className="btn" onClick={again}>← Change the fly</button>
        <button className="btn" onClick={() => nav('/scene')}>Change the scene</button>
      </div>
    </div>
  )
}
