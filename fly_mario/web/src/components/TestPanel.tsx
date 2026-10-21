import { useState } from 'react'
import { api } from '../api/client'
import type { DevSetResult } from '../api/models'
import { eta, isLive, useJob } from '../jobs'
import VideoExport from './VideoExport'

const DIALS: [string, string][] = [['original', 'Original'], ['tuned', 'Tuned']]
const OUTCOME: Record<string, string> = { flag: 'reached the flag', died: 'died', stuck: 'got stuck', timeout: 'ran out of time' }

/** One dials setting's ten starts, a row each: how it ended, how far, and what the fly did on the way. */
export interface Pick { dials: string; start: number }
const samePick = (a: Pick, b: Pick) => a.dials === b.dials && a.start === b.start

export function StartRows({ result, dials, picked, onPick, onPair }: {
  result: DevSetResult; dials?: string; picked?: Pick[]; onPick?: (p: Pick) => void; onPair?: (start: number) => void
}) {
  return (
    <div className="start-rows" data-testid="start-rows" role="table">
      <div className="sr head" role="row">
        <span>Start</span><span>Outcome</span><span>Distance</span><span>Score</span><span>Jumps</span><span>Back-ups</span><span>Blocks</span><span>Mushroom</span>{onPick && <span>Video</span>}
      </div>
      {result.episodes.map((e, i) => (
        <div className={`sr ${e.outcome === 'flag' ? 'ok' : ''} ${onPick ? 'pickable' : ''}`} role="row" key={e.label} data-testid="start-row" data-outcome={e.outcome}>
          <span>{onPick && dials ? <label className="check"><input type="checkbox" aria-label={`pick ${e.label}`} checked={!!picked?.some((p) => samePick(p, { dials, start: i + 1 }))}
            onChange={() => onPick({ dials, start: i + 1 })} />{e.label}</label> : e.label}</span>
          <span className={e.outcome === 'flag' ? 'ok' : 'bad'}>{OUTCOME[e.outcome] ?? e.outcome}{e.death?.object_label ? ` · ${e.death.object_label}` : ''}</span>
          <span>x {Math.round(e.max_x)}</span><span>{Math.round(e.score)}</span><span>{e.jumps}</span><span>{e.back_ups}</span><span>{e.blocks}</span>
          <span>{e.mushroom ? 'got it' : '–'}</span>
          {onPick && <span>{onPair && <button className="btn sm" onClick={() => onPair(i + 1)} title="Original dials and Tuned dials, from this start">Original vs Tuned</button>}</span>}
        </div>
      ))}
    </div>
  )
}

/** "Test this fly": progress while the 10 starts are played, then "Original 8/10 · Tuned 10/10" and a row per start. */
export default function TestPanel({ jobId, onClose }: { jobId: string; onClose?: () => void }) {
  const job = useJob(jobId)
  const [pick, setPick] = useState<string | null>(null)
  const [picked, setPicked] = useState<Pick[]>([])
  const [pair, setPair] = useState<[Pick, Pick] | null>(null)
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
              <StartRows result={d.results[shown]} dials={shown} picked={picked}
                onPick={(p) => setPicked((cur) => (cur.some((c) => samePick(c, p)) ? cur.filter((c) => !samePick(c, p)) : [...cur, p].slice(-2)))}
                onPair={have.length === 2 ? (start) => setPair([{ dials: 'original', start }, { dials: 'tuned', start }]) : undefined} />
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn" disabled={picked.length !== 2} onClick={() => setPair([picked[0], picked[1]])}>Side by side ({picked.length}/2 picked)</button>
                <small className="muted">Tick two runs (they must share a start), or use "Original vs Tuned" on a row.</small>
              </div>
              {pair && <PairVideo key={pair.map((p) => `${p.dials}${p.start}`).join()} jobId={d.id} pair={pair} onClose={() => setPair(null)} />}
            </>
          )}
        </>
      )}
    </section>
  )
}

/** The side-by-side of two runs of a test: the options, then the shared preview-then-render panel. */
function PairVideo({ jobId, pair, onClose }: { jobId: string; pair: [Pick, Pick]; onClose: () => void }) {
  const [brain, setBrain] = useState(false)
  const [speed, setSpeed] = useState(1)
  return (
    <VideoExport label="Side by side" onClose={onClose}
      build={() => ({ export: 'side_by_side', show_brain: brain, speed,
        a: { job_id: jobId, start: pair[0].start, dials: pair[0].dials as 'original' | 'tuned' },
        b: { job_id: jobId, start: pair[1].start, dials: pair[1].dials as 'original' | 'tuned' } })}>
      <div className="toolrow">
        <label className="check"><input type="checkbox" checked={brain} onChange={(e) => setBrain(e.target.checked)} />Show brain (small, under each game)</label>
        <div className="speeds" role="group" aria-label="video speed">
          {[1, 2].map((v) => <button key={v} className={`chip ${speed === v ? 'on' : ''}`} aria-pressed={speed === v} onClick={() => setSpeed(v)}>{v}×</button>)}
        </div>
      </div>
    </VideoExport>
  )
}
