import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { DevSetResult, JobDetail } from '../api/models'
import LiveRun from '../components/LiveRun'
import TestPanel from '../components/TestPanel'
import { errText } from '../hooks'
import { defaultScene, useDraft } from '../draft'
import { eta, isLive, useJob } from '../jobs'

/** The chart of the wireframe: per generation a grey bar (the average) and a gold one (the best). Click one to watch. */
function Bars({ job, picked, onPick }: { job: JobDetail; picked: number | null; onPick: (gen: number) => void }) {
  const bars = job.progress.bars
  const top = Math.max(1e-9, ...bars.flatMap((b) => [b.best, b.mean]))
  const h = (v: number) => `${Math.max(2, (Math.max(v, 0) / top) * 100)}%`
  return (
    <>
      <div className="bars" data-testid="bars" role="group" aria-label="generations">
        {bars.map((b) => (
          <button key={b.gen} className={`gen ${picked === b.gen ? 'on' : ''}`} data-testid="gen-bar" aria-label={`generation ${b.gen}`}
            aria-pressed={picked === b.gen} title={`generation ${b.gen}: click to watch its best fly`} onClick={() => onPick(b.gen)}>
            <i className="avg" style={{ height: h(b.mean) }} /><i className="best" style={{ height: h(b.best) }} />
          </button>
        ))}
        {bars.length === 0 && <p className="muted">The first generation is still being played…</p>}
      </div>
      <div className="row spread axis">
        <span>generation 0</span>
        <span>{bars.length > 1 ? `generation ${bars[bars.length - 1].gen}` : ''}</span>
      </div>
    </>
  )
}

const flagsText = (r: DevSetResult) => `${r.flags} of ${r.n}`

function Changes({ job }: { job: JobDetail }) {
  return (
    <aside className="box what-changed" data-testid="what-changed">
      <h2 className="label">What evolution changed</h2>
      <p className="lead" style={{ marginTop: 0 }}>Compared with where it started. Senses you switched off were never touched.</p>
      {isLive(job.status) && <p className="muted" style={{ marginTop: 16 }}>Shown when the evolution has finished.</p>}
      {job.changes.filter((c) => c.direction !== 'same').map((c) => (
        <div className="change" key={c.key} data-testid="change">
          <span>{c.label}</span>
          <span className={c.direction === 'same' ? 'same' : 'moved'}>{c.words}</span>
        </div>
      ))}
      {job.changes.length > 0 && job.changes.every((c) => c.direction === 'same') && <p className="muted" style={{ marginTop: 12 }}>Evolution left every knob about where it was.</p>}
      {job.changes.some((c) => c.direction === 'same') && job.changes.some((c) => c.direction !== 'same') && (
        <div className="change"><span>Everything else</span><span className="same">about the same</span></div>
      )}
      {job.dev_best && (
        <p className="note" style={{ color: '#d8d8d8' }} data-testid="dev-result">
          Tested once on unseen starts: reached the flag {flagsText(job.dev_best)} times
          {job.dev_start ? ` (the fly it started from: ${flagsText(job.dev_start)}).` : '.'}
        </p>
      )}
    </aside>
  )
}

/** /evolution/:id. A test job opened here shows its result panel instead. */
export default function EvolutionScreen() {
  const { id = '' } = useParams()
  const job = useJob(id)
  if (!job.data) return <p>{job.isError ? 'No such job.' : 'Loading…'}</p>
  if (job.data.kind === 'test') return <><Link className="back" to="/library">‹ Library</Link><TestPanel jobId={id} /></>
  return <EvolutionView job={job.data} />
}

function EvolutionView({ job }: { job: JobDetail }) {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { setFly } = useDraft()
  const [picked, setPicked] = useState<number | null>(null)
  const [watch, setWatch] = useState<{ gen: number; runId: string } | null>(null)
  const [error, setError] = useState('')
  const p = job.progress
  const live = isLive(job.status)
  const best = job.best_generation ?? null

  const pick = async (gen: number) => {
    setPicked(gen); setError('')
    try {
      const fly = await api.getGenerationFly(job.id, gen)
      const { run_id } = await api.startRun({ fly, scene: { ...defaultScene, level_id: job.level_id }, from_moment: null, dials: 'tuned' })
      setWatch({ gen, runId: run_id })
    } catch (e) { setError(errText(e)) }
  }
  const use = useMutation({
    mutationFn: () => api.useEvolvedFly(job.id),
    onSuccess: (fly) => { setFly(fly); qc.invalidateQueries({ queryKey: ['registry'] }); qc.invalidateQueries({ queryKey: ['job', job.id] }) },
  })
  const cancel = useMutation({ mutationFn: () => api.cancelJob(job.id), onSuccess: () => qc.invalidateQueries({ queryKey: ['job', job.id] }) })
  const saved = use.data?.name ?? job.saved_as

  return (
    <div className="evo" data-testid="evolution" data-status={job.status}>
      <Link className="back" to="/library">‹ Library</Link>
      <div className="row spread" style={{ alignItems: 'flex-start' }}>
        <div>
          <h1 className="title">Evolution {job.fly}</h1>
          <p className="lead">
            Started from {job.fly} · trained on {job.level_id} · {job.generations} generations · ran in the background
            {job.start !== 'level_start' ? ' · from a saved moment' : ''}
          </p>
        </div>
        <div className="row">
          {live && <button className="btn" onClick={() => cancel.mutate()} disabled={cancel.isPending}>Cancel</button>}
          {saved
            ? <button className="btn gold" onClick={() => nav('/fly')}>Saved as {saved} · open it</button>
            : <button className="btn gold" disabled={job.status !== 'finished' || use.isPending} onClick={() => use.mutate()}>Use the best fly</button>}
        </div>
      </div>

      {live && (
        <section className="box job-progress-box" data-testid="evo-progress">
          <div className="pbar" role="progressbar"><i style={{ width: `${job.generations ? (p.generation / job.generations) * 100 : 0}%` }} /></div>
          <p>
            {p.phase === 'dev set' ? 'Testing the best fly on 10 unseen starts…' : p.phase === 'training' || p.phase === 'done'
              ? `Generation ${p.generation} of ${job.generations} done` : 'Starting up…'} · {eta(p.eta_s)}
          </p>
        </section>
      )}
      {job.status === 'failed' && <div className="banner died" role="alert"><div><b>The evolution failed</b><p>{job.error}</p></div></div>}
      {job.status === 'cancelled' && <p className="muted">Cancelled. The generations so far are below.</p>}

      <section className="box chart">
        <div className="row spread">
          <h2 className="label" style={{ margin: 0 }}>How the best fly improved</h2>
          <div className="legend-row"><span><i className="sw best" />best of the generation</span><span><i className="sw avg" />average</span></div>
        </div>
        <Bars job={job} picked={picked ?? (watch ? watch.gen : null)} onPick={pick} />
      </section>

      <div className="evo-cols">
        <section>
          <h2 className="gen-title">{picked != null ? `Generation ${picked} · best fly` : best != null && !live ? `Generation ${best} · best fly overall` : 'Best fly'}</h2>
          <div className={`watch ${watch ? 'on' : ''}`}>
            {watch ? <LiveRun key={watch.runId} runId={watch.runId} /> : <p className="muted">[that generation&apos;s best run · brain | game]</p>}
          </div>
          <p className="muted" style={{ marginTop: 10 }}>Click any bar above to watch that generation&apos;s best fly.</p>
          {error && <p className="err" role="alert">{error}</p>}
          {use.isError && <p className="err" role="alert">{errText(use.error)}</p>}
        </section>
        <Changes job={job} />
      </div>
    </div>
  )
}
