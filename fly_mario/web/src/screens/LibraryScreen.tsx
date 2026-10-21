import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api, videoUrl } from '../api/client'
import VideoExport from '../components/VideoExport'
import { loadScenes, useDraft } from '../draft'
import { eta, isLive } from '../jobs'

/** Everything saved: flies (on the server), scenes (in this browser) and finished runs. */
export default function LibraryScreen() {
  const nav = useNavigate()
  const { setFly, setScene } = useDraft()
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const runs = useQuery({ queryKey: ['runs'], queryFn: api.getRuns, staleTime: 0 })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.getJobs, staleTime: 0, refetchInterval: 3000 })
  const videos = useQuery({ queryKey: ['videos'], queryFn: api.getVideos, staleTime: 0, refetchInterval: 3000 })
  const [tab, setTab] = useState<'saved' | 'evolutions' | 'videos'>('saved')
  const [picked, setPicked] = useState<string[]>([])
  const [pair, setPair] = useState<[string, string] | null>(null)
  const scenes = loadScenes()
  return (
    <>
      <h1 className="title">Library</h1>
      <p className="lead">Flies and scenes to start from again, every run so far, and the evolutions and tests that ran in the background.</p>
      <div className="dials" role="tablist" aria-label="library tabs">
        {([['saved', 'Saved'], ['evolutions', 'Evolutions'], ['videos', 'Videos']] as const).map(([k, l]) => (
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
      {tab === 'videos' && (
        <section className="box" data-testid="videos-list" style={{ marginTop: 18 }}>
          <h2 className="label">Videos</h2>
          {videos.data?.length ? videos.data.map((v) => (
            <div className="lib-row" key={v.id} data-testid="video-row" data-status={v.status} data-stage={v.stage}>
              <span>
                {v.title}
                <small className="muted" style={{ display: 'block' }}>
                  {v.video ? `${v.duration_s?.toFixed(0)} s · ${v.size_mb} MB · 1920×1080, 60 fps`
                    : v.status === 'failed' ? `failed: ${v.error}`
                    : isLive(v.status) ? (v.stage === 'stills' ? 'making preview stills…' : `rendering ${v.progress.total ? Math.round((v.progress.done / v.progress.total) * 100) : 0}% · ${eta(v.progress.eta_s)}`)
                    : v.status === 'cancelled' ? 'cancelled' : 'preview stills ready: not rendered yet'}
                </small>
              </span>
              <span className="row">
                {v.stills.slice(0, 1).map((s) => <a key={s} href={videoUrl(s)} target="_blank" rel="noreferrer"><img className="video-thumb" src={videoUrl(s)} alt="preview" /></a>)}
                {v.video && <a className="btn gold sm" href={videoUrl(v.video, true)} download data-testid="video-download">Download</a>}
                {!v.video && v.stage === 'stills' && v.status === 'finished' && <button className="btn sm" onClick={() => api.renderVideo(v.id).then(() => videos.refetch())}>Render video</button>}
              </span>
            </div>
          )) : <p className="muted">No video exported yet. Use “Download video” on a finished run, “Side by side” on a test or on two runs here, or “Download montage” on an evolution.</p>}
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
          <div className="row spread">
            <h2 className="label" style={{ margin: 0 }}>Runs</h2>
            <button className="btn sm" disabled={picked.length !== 2} onClick={() => setPair([picked[0], picked[1]])} data-testid="side-by-side">Side by side ({picked.length}/2)</button>
          </div>
          {runs.data?.length ? [...runs.data].reverse().slice(0, 40).map((r) => (
            <div className="lib-row" key={r.id}>
              <label className="check"><input type="checkbox" aria-label={`pick run ${r.id}`} disabled={r.status !== 'finished'} checked={picked.includes(r.id)}
                onChange={() => setPicked((cur) => (cur.includes(r.id) ? cur.filter((c) => c !== r.id) : [...cur, r.id].slice(-2)))} />
                {r.fly} · {r.level_id} · {r.dials === 'original' ? 'original dials' : 'tuned dials'}</label>
              <span className={r.outcome === 'flag' ? 'ok' : 'bad'}>{r.outcome ? `${r.outcome} x ${Math.round(r.max_x ?? 0)}` : r.status}</span>
            </div>
          )) : <p className="muted">No runs yet.</p>}
        </section>
      </div>
      {pair && <LibraryPair key={pair.join()} ids={pair} onClose={() => setPair(null)} />}
    </>
  )
}

/** Two saved runs from the same start, side by side. */
function LibraryPair({ ids, onClose }: { ids: [string, string]; onClose: () => void }) {
  const [brain, setBrain] = useState(false)
  const [speed, setSpeed] = useState(1)
  return (
    <VideoExport label="Side by side" onClose={onClose}
      build={() => ({ export: 'side_by_side', show_brain: brain, speed, a: { run_id: ids[0] }, b: { run_id: ids[1] } })}>
      <div className="toolrow">
        <label className="check"><input type="checkbox" checked={brain} onChange={(e) => setBrain(e.target.checked)} />Show brain (small, under each game)</label>
        <div className="speeds" role="group" aria-label="video speed">
          {[1, 2].map((v) => <button key={v} className={`chip ${speed === v ? 'on' : ''}`} aria-pressed={speed === v} onClick={() => setSpeed(v)}>{v}×</button>)}
        </div>
      </div>
    </VideoExport>
  )
}
