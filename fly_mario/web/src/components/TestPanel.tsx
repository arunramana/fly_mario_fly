import { useState } from 'react'
import { api } from '../api/client'
import type { DevSetResult } from '../api/models'
import { eta, isLive, useJob } from '../jobs'

const DIALS: [string, string][] = [['original', 'Original'], ['tuned', 'Tuned']]
const OUTCOME: Record<string, string> = { flag: 'reached the flag', died: 'died', stuck: 'got stuck', timeout: 'ran out of time' }

/** One dials setting's ten starts, a row each: how it ended, how far, and what the fly did on the way. */
export function StartRows({ result }: { result: DevSetResult }) {
  return (
    <div className="start-rows" data-testid="start-rows" role="table">
      <div className="sr head" role="row">
        <span>Start</span><span>Outcome</span><span>Distance</span><span>Score</span><span>Jumps</span><span>Back-ups</span><span>Blocks</span><span>Mushroom</span>
      </div>
      {result.episodes.map((e) => (
        <div className={`sr ${e.outcome === 'flag' ? 'ok' : ''}`} role="row" key={e.label} data-testid="start-row" data-outcome={e.outcome}>
          <span>{e.label}</span>
          <span className={e.outcome === 'flag' ? 'ok' : 'bad'}>{OUTCOME[e.outcome] ?? e.outcome}{e.death?.object_label ? ` · ${e.death.object_label}` : ''}</span>
          <span>x {Math.round(e.max_x)}</span><span>{Math.round(e.score)}</span><span>{e.jumps}</span><span>{e.back_ups}</span><span>{e.blocks}</span>
          <span>{e.mushroom ? 'got it' : '–'}</span>
        </div>
      ))}
    </div>
  )
}

/** "Test this fly": progress while the 10 starts are played, then "Original 8/10 · Tuned 10/10" and a row per start. */
export default function TestPanel({ jobId, onClose }: { jobId: string; onClose?: () => void }) {
  const job = useJob(jobId)
  const [pick, setPick] = useState<string | null>(null)
  const d = job.data
  if (!d) return <section className="box test-panel"><p className="muted">Starting the test…</p></section>
  const have = DIALS.filter(([k]) => d.results[k])
  const shown = d.results[pick ?? ''] ? pick! : have.length ? have[have.length - 1][0] : ''
  const p = d.progress
  return (
    <section className="box test-panel" data-testid="test-panel" data-status={d.status}>
      <div className="row spread">
        <h2 className="label" style={{ margin: 0 }}>{d.title}</h2>
        {onClose && <button className="btn sm" onClick={onClose} aria-label="close test">Close</button>}
      </div>
      {isLive(d.status) && (
        <div className="job-progress">
          <div className="pbar" role="progressbar"><i style={{ width: `${p.total ? (p.done / p.total) * 100 : 3}%` }} /></div>
          <p>{p.phase === 'testing' ? `Played ${p.done} of ${p.total} runs` : 'Starting up…'} · {eta(p.eta_s)}</p>
          <button className="btn sm" onClick={() => api.cancelJob(d.id).then(() => job.refetch())}>Cancel</button>
        </div>
      )}
      {d.status === 'failed' && <p className="err" role="alert">The test failed: {d.error}</p>}
      {d.status === 'cancelled' && <p className="muted">Cancelled.</p>}
      {d.status === 'finished' && have.length > 0 && (
        <>
          <div className="row" style={{ marginTop: 12 }}>
            <b className="headline" data-testid="test-headline">{d.headline}</b>
            <span className="muted">reached the flag, from 10 starts the fly was never tuned on</span>
          </div>
          <div className="dials" role="group" aria-label="test dials">
            {have.map(([k, label]) => (
              <button key={k} className={`chip ${shown === k ? 'on' : ''}`} aria-pressed={shown === k} onClick={() => setPick(k)}>
                {label} {d.results[k].flags}/{d.results[k].n}
              </button>
            ))}
          </div>
          {shown && (
            <>
              <p className="muted" style={{ marginBottom: 10 }}>
                On average it got as far as x {Math.round(d.results[shown].mean_max_x)}; its worst start reached x {Math.round(d.results[shown].min_max_x)}; mean score {Math.round(d.results[shown].mean_score)}.
              </p>
              <StartRows result={d.results[shown]} />
            </>
          )}
        </>
      )}
    </section>
  )
}
