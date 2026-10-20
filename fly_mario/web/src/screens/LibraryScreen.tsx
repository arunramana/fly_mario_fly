import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { loadScenes, useDraft } from '../draft'

/** Everything saved: flies (on the server), scenes (in this browser) and finished runs. */
export default function LibraryScreen() {
  const nav = useNavigate()
  const { setFly, setScene } = useDraft()
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const runs = useQuery({ queryKey: ['runs'], queryFn: api.getRuns, staleTime: 0 })
  const scenes = loadScenes()
  return (
    <>
      <h1 className="title">Library</h1>
      <p className="lead">Flies and scenes to start from again, and every run so far.</p>
      <div className="lib">
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
              <span>{r.fly} · {r.level_id}</span>
              <span className={r.outcome === 'flag' ? 'ok' : 'bad'}>{r.outcome ? `${r.outcome} x ${Math.round(r.max_x ?? 0)}` : r.status}</span>
            </div>
          )) : <p className="muted">No runs yet.</p>}
        </section>
      </div>
    </>
  )
}
