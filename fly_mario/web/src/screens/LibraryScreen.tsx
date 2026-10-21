import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { loadScenes, useDraft } from '../draft'
import { eta, isLive } from '../jobs'

/** Everything saved: flies (on the server), scenes (in this browser) and finished runs. */
export default function LibraryScreen() {
  const nav = useNavigate()
  const { setFly, setScene } = useDraft()
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const runs = useQuery({ queryKey: ['runs'], queryFn: api.getRuns, staleTime: 0 })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.getJobs, staleTime: 0, refetchInterval: 3000 })
  const [tab, setTab] = useState<'saved' | 'evolutions'>('saved')
  const scenes = loadScenes()
  return (
    <>
      <h1 className="title">Library</h1>
      <p className="lead">Flies and scenes to start from again, every run so far, and the evolutions and tests that ran in the background.</p>
      <div className="dials" role="tablist" aria-label="library tabs">
        {([['saved', 'Saved'], ['evolutions', 'Evolutions']] as const).map(([k, l]) => (
          <button key={k} role="tab" className={`chip ${tab === k ? 'on' : ''}`} aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === 'evolutions' && (
        <section className="box" data-testid="evolutions-list" style={{ marginTop: 18 }}>
          <h2 className="label">Evolutions and tests</h2>
          {jobs.data?.length ? jobs.data.map((j) => (
            <div className="lib-row" key={j.id} data-testid="job-row">
              <span>
                <Link to={`/evolution/${encodeURIComponent(j.id)}`}>{j.title}</Link>
                <small className="muted" style={{ display: 'block' }}>
                  {isLive(j.status) ? (j.kind === 'evolve' ? `generation ${j.progress.generation} of ${j.progress.generations} · ` : `${j.progress.done} of ${j.progress.total} runs · `) + eta(j.progress.eta_s)
                    : j.status === 'finished' ? j.headline : j.status}
                </small>
              </span>
              <Link className="btn sm" to={`/evolution/${encodeURIComponent(j.id)}`}>Open</Link>
            </div>
          )) : <p className="muted">Nothing yet. Press “Evolve this fly” or “Test this fly” on the Fly page.</p>}
        </section>
      )}
      <div className="lib" style={tab === 'saved' ? undefined : { display: 'none' }}>
        <section className="box">
          <h2 className="label">Flies</h2>
          {registry.data?.presets.map((p) => (
            <div className="lib-row" key={p}>
              <span>{p}</span>
              <button className="btn sm" onClick={async () => { setFly(await api.getFly(p)); nav('/fly') }}>Use</button>
            </div>
          ))}
        </section>
        <section className="box">
          <h2 className="label">Scenes</h2>
          {scenes.length ? scenes.map((s) => (
            <div className="lib-row" key={s.name}>
              <span>{s.name}</span>
              <button className="btn sm" onClick={() => { setScene(s.scene); nav('/scene') }}>Use</button>
            </div>
          )) : <p className="muted">No scene saved yet. Press “Save scene” on the Scene page.</p>}
        </section>
        <section className="box">
          <h2 className="label">Runs</h2>
          {runs.data?.length ? [...runs.data].reverse().slice(0, 40).map((r) => (
            <div className="lib-row" key={r.id}>
              <span>{r.fly} · {r.level_id} · {r.dials === 'original' ? 'original dials' : 'tuned dials'}</span>
              <span className={r.outcome === 'flag' ? 'ok' : 'bad'}>{r.outcome ? `${r.outcome} x ${Math.round(r.max_x ?? 0)}` : r.status}</span>
            </div>
          )) : <p className="muted">No runs yet.</p>}
        </section>
      </div>
    </>
  )
}
