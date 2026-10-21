import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, videoUrl } from '../api/client'
import type { Fly, JobDetail } from '../api/models'
import DownloadButton from '../components/DownloadButton'
import TestResult from '../components/TestResult'
import { errText } from '../hooks'
import { useDraft } from '../draft'
import { eta, isLive, useJob } from '../jobs'

const GENERATIONS = [2, 5, 10, 15, 30]

/** The Evolution tab: start an evolution or a test on the left, and the evolutions made so far; the one opened on the right. */
export default function EvolutionScreen() {
  const { id = '' } = useParams()
  return (
    <div className="evo-page">
      <section className="evo-left">
        <Start />
        <EvolutionList openId={id} />
      </section>
      <section className="evo-right">
        {id ? <EvolutionDetail key={id} id={id} /> : <div className="box"><p className="muted">Open an evolution from the list to see what it changed.</p></div>}
      </section>
    </div>
  )
}

/** "Evolve" and "Test this fly (10 starts)": both run in the background. */
function Start() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { scene, fly: draftFly, dials: draftDials, lastRunId } = useDraft()
  const [flyName, setFlyName] = useState('')                 // '' = the fly being built on the Fly tab
  const [dials, setDials] = useState(draftDials)
  const [level, setLevel] = useState(scene.level_id)
  const [gens, setGens] = useState(10)
  const [start, setStart] = useState('level_start')
  const [quick, setQuick] = useState(false)
  const [testId, setTestId] = useState<string | null>(null)
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const moments = useQuery({ queryKey: ['moments', lastRunId], queryFn: () => api.getRunMoments(lastRunId!), enabled: !!lastRunId, staleTime: 5_000 })
  const here = (moments.data ?? []).filter((m) => m.scene.level_id === level)
  const presets = registry.data?.presets ?? []
  const theFly = async (): Promise<Fly> => (flyName ? api.getFly(flyName) : draftFly)

  const evolve = useMutation({
    mutationFn: async () => api.startEvolve({ fly: await theFly(), dials, level, generations: gens, start, ...(quick ? { population: 4, train_n: 2 } : {}) }),
    onSuccess: (id) => { qc.invalidateQueries({ queryKey: ['jobs'] }); nav(`/evolution/${id}`) },
  })
  const test = useMutation({
    mutationFn: async () => api.startTest({ fly: await theFly(), dials: 'both', level }),
    onSuccess: (id) => setTestId(id),
  })

  return (
    <section className="box" data-testid="evolve-panel">
      <h2 className="label">Evolve</h2>
      <div className="evolve-form">
        <label>Fly
          <select aria-label="evolve fly" value={flyName} onChange={(e) => setFlyName(e.target.value)}>
            <option value="">{draftFly.name} (from the Fly tab)</option>
            {presets.filter((p) => p !== draftFly.name).map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label>Dials
          <select aria-label="evolve dials" value={dials} onChange={(e) => setDials(e.target.value as 'original' | 'tuned')}>
            <option value="tuned">Tuned</option>
            <option value="original">Original</option>
          </select>
        </label>
        <label>Level
          <select aria-label="evolve level" value={level} onChange={(e) => { setLevel(e.target.value); setStart('level_start') }}>
            {(levels.data ?? [{ id: level, label: level }]).map((l) => <option key={l.id} value={l.id}>{l.id === l.label ? l.id : `${l.id} ${l.label}`}</option>)}
          </select>
        </label>
        <label>Generations
          <select aria-label="generations" value={gens} onChange={(e) => setGens(Number(e.target.value))}>
            {GENERATIONS.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
        <label>Start from
          <select aria-label="start from" value={start} onChange={(e) => setStart(e.target.value)}>
            <option value="level_start">the level start</option>
            {here.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" aria-label="quick try" checked={quick} onChange={(e) => setQuick(e.target.checked)} />
          Quick try (a small search)
        </label>
      </div>
      <div className="row" style={{ marginTop: 14 }}>
        <button className="btn gold" onClick={() => evolve.mutate()} disabled={evolve.isPending}>Evolve</button>
        <button className="btn" onClick={() => test.mutate()} disabled={test.isPending}>Test this fly (10 starts)</button>
      </div>
      {evolve.isError && <p className="err" role="alert">{errText(evolve.error)}</p>}
      {test.isError && <p className="err" role="alert">{errText(test.error)}</p>}
      {testId && <div className="start-test"><TestResult key={testId} jobId={testId} /></div>}
    </section>
  )
}

function EvolutionList({ openId }: { openId: string }) {
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.getJobs, staleTime: 0, refetchInterval: 3000 })
  const evolutions = (jobs.data ?? []).filter((j) => j.kind === 'evolve')
  return (
    <section className="box evo-list" data-testid="evolutions-list">
      <h2 className="label">Evolutions</h2>
      <div className="evo-list-body">
        {evolutions.length ? evolutions.map((j) => (
          <Link key={j.id} to={`/evolution/${encodeURIComponent(j.id)}`} className={`lib-row evo-row ${j.id === openId ? 'on' : ''}`} data-testid="job-row">
            <span>
              {j.title}
              <small className="muted" style={{ display: 'block' }}>
                {isLive(j.status) ? `generation ${j.progress.generation} of ${j.progress.generations} · ${eta(j.progress.eta_s)}` : j.status === 'finished' ? j.headline : j.status}
              </small>
            </span>
          </Link>
        )) : <p className="muted">None yet. Press Evolve.</p>}
      </div>
    </section>
  )
}

/** The chart: per generation a grey bar (the average) and a gold one (the best). */
function Graph({ job }: { job: JobDetail }) {
  const bars = job.progress.bars
  const top = Math.max(1e-9, ...bars.flatMap((b) => [b.best, b.mean]))
  const h = (v: number) => `${Math.max(2, (Math.max(v, 0) / top) * 100)}%`
  return (
    <section className="box chart">
      <div className="row spread">
        <h2 className="label" style={{ margin: 0 }}>Fitness of each generation</h2>
        <div className="legend-row"><span><i className="sw best" />best</span><span><i className="sw avg" />average</span></div>
      </div>
      <div className="bars" data-testid="bars" role="img" aria-label="best and average fitness per generation">
        {bars.map((b) => (
          <div key={b.gen} className="gen" data-testid="gen-bar" title={`generation ${b.gen}: best ${b.best.toFixed(2)}, average ${b.mean.toFixed(2)}`}>
            <i className="avg" style={{ height: h(b.mean) }} /><i className="best" style={{ height: h(b.best) }} />
          </div>
        ))}
        {bars.length === 0 && <p className="muted">The first generation is still being played…</p>}
      </div>
      <div className="row spread axis">
        <span>generation 0</span>
        <span>{bars.length > 1 ? `generation ${bars[bars.length - 1].gen}` : ''}</span>
      </div>
    </section>
  )
}

function EvolutionDetail({ id }: { id: string }) {
  const job = useJob(id)
  if (!job.data) return <div className="box"><p>{job.isError ? 'No such evolution.' : 'Loading…'}</p></div>
  return <EvolutionView job={job.data} />
}

function EvolutionView({ job }: { job: JobDetail }) {
  const qc = useQueryClient()
  const { setFly } = useDraft()
  const [name, setName] = useState('')
  const live = isLive(job.status)
  const p = job.progress
  const videos = useQuery({ queryKey: ['videos'], queryFn: api.getVideos, staleTime: 0, refetchInterval: 5000 })
  const montage = (videos.data ?? []).find((v) => v.export === 'montage' && v.of === job.id && v.status === 'finished' && v.video)
  const cancel = useMutation({ mutationFn: () => api.cancelJob(job.id), onSuccess: () => qc.invalidateQueries({ queryKey: ['job', job.id] }) })
  const save = useMutation({
    mutationFn: () => api.useEvolvedFly(job.id, name.trim()),
    onSuccess: (fly) => { setFly(fly); qc.invalidateQueries({ queryKey: ['registry'] }); qc.invalidateQueries({ queryKey: ['job', job.id] }) },
  })
  const saved = save.data?.name ?? job.saved_as

  return (
    <div className="evo" data-testid="evolution" data-status={job.status}>
      <div className="row spread">
        <div>
          <h1 className="title">{job.title}</h1>
          <p className="lead">{job.generations} generations{job.start !== 'level_start' ? ' · from a saved moment' : ''} · {job.status}{job.headline ? ` · ${job.headline}` : ''}</p>
        </div>
        {live && <button className="btn" onClick={() => cancel.mutate()} disabled={cancel.isPending}>Cancel</button>}
      </div>
      {live && (
        <div className="job-progress-box" data-testid="evo-progress">
          <div className="pbar" role="progressbar"><i style={{ width: `${job.generations ? (p.generation / job.generations) * 100 : 0}%` }} /></div>
          <p>
            {p.phase === 'dev set' ? 'Testing the best fly on 10 unseen starts…' : p.phase === 'training' || p.phase === 'done'
              ? `Generation ${p.generation} of ${job.generations} done` : 'Starting up…'} · {eta(p.eta_s)}
          </p>
        </div>
      )}
      {job.status === 'failed' && <div className="banner died" role="alert"><div><b>The evolution failed</b><p>{job.error}</p></div></div>}

      <section className="box what-changed" data-testid="what-changed">
        <h2 className="label">What is being evolved</h2>
        {live && <p className="muted">Shown when the evolution has finished.</p>}
        {job.changes.map((c) => (
          <div className="change" key={c.key} data-testid="change">
            <span>{c.label}{c.owner && <small className="muted"> · {c.owner}</small>}</span>
            <span className={c.direction === 'same' ? 'same' : 'moved'}>{c.words}</span>
          </div>
        ))}
        {!live && job.changes.length === 0 && <p className="muted">Nothing to show.</p>}
      </section>

      <Graph job={job} />

      <section className="box montage" data-testid="montage">
        <div className="row spread">
          <h2 className="label" style={{ margin: 0 }}>Montage</h2>
          <DownloadButton label="Download montage" disabled={p.bars.length === 0} readyPath={montage?.video}
            title="One short clip per generation's best fly, with the fitness chart underneath"
            build={() => ({ export: 'montage', job_id: job.id })} onDone={() => videos.refetch()} />
        </div>
        {montage?.video
          ? <video className="montage-video" data-testid="montage-video" src={videoUrl(montage.video)} controls preload="metadata" />
          : <p className="muted">One short clip per generation&apos;s best fly. Press Download montage to make it; it plays here once it is made.</p>}
      </section>

      <section className="box save-fly">
        <h2 className="label">Save as fly</h2>
        {saved ? <p className="ok" data-testid="saved-as">Saved as {saved}. It is in the Fly tab&apos;s presets.</p> : (
          <div className="namebar">
            <input type="text" aria-label="evolved fly name" placeholder="name (blank: its own name)" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn gold" disabled={job.status !== 'finished' || save.isPending} onClick={() => save.mutate()}>Save as fly</button>
          </div>
        )}
        {save.isError && <p className="err" role="alert">{errText(save.error)}</p>}
      </section>
    </div>
  )
}
