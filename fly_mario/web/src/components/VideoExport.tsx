import { useState, type ReactNode } from 'react'
import { api, videoUrl } from '../api/client'
import type { VideoRequest } from '../api/models'
import { errText } from '../hooks'
import { eta, isLive, useVideo } from '../jobs'

/** The same two steps for every export: look at 2-3 stills first, then "Render video"; the mp4 downloads when it is done.
 *  `children` are the export's options; they lock once the preview is made ("Change options" starts over). */
export default function VideoExport({ build, label, children, onClose }: {
  build: () => VideoRequest; label: string; children?: ReactNode; onClose?: () => void
}) {
  const [id, setId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const video = useVideo(id)
  const v = video.data

  const run = async (f: () => Promise<unknown>) => {
    setError(''); setBusy(true)
    try { await f() } catch (e) { setError(errText(e)) } finally { setBusy(false) }
  }
  const make = () => run(async () => { setId((await api.startVideo(build())).id) })
  const render = () => run(async () => { await api.renderVideo(id!); await video.refetch() })
  const cancel = () => run(async () => { await api.cancelVideo(id!); await video.refetch() })

  const making = !!v && v.stage === 'stills' && isLive(v.status)
  const ready = !!v && v.stage === 'stills' && v.status === 'finished'
  const rendering = !!v && v.stage === 'video' && isLive(v.status)
  const done = !!v && v.stage === 'video' && v.status === 'finished' && !!v.video
  const p = v?.progress

  return (
    <section className="box video-export" data-testid="video-export" data-stage={v?.stage ?? 'options'} data-status={v?.status ?? ''}>
      <div className="row spread">
        <h2 className="label" style={{ margin: 0 }}>{label}</h2>
        {onClose && <button className="btn sm" onClick={onClose} aria-label="close video export">Close</button>}
      </div>
      <fieldset className="video-options" disabled={!!id}>{children}</fieldset>

      {!id && <div className="row" style={{ marginTop: 12 }}><button className="btn gold" onClick={make} disabled={busy}>Make preview stills</button>
        <small className="muted">Nothing is rendered until you have looked at them.</small></div>}

      {making && (
        <div className="job-progress">
          <div className="pbar" role="progressbar"><i style={{ width: `${p && p.total ? (p.done / p.total) * 100 : 5}%` }} /></div>
          <p>Making preview stills… (replaying the run{p?.eta_s != null ? `, ${eta(p.eta_s)}` : ''})</p>
          <button className="btn sm" onClick={cancel}>Cancel</button>
        </div>
      )}

      {v && v.stills.length > 0 && (
        <div className="video-stills" data-testid="video-stills">
          {v.stills.map((s, i) => <a key={s} href={videoUrl(s)} target="_blank" rel="noreferrer"><img src={videoUrl(s)} alt={`preview ${i + 1}`} data-testid="video-still" /></a>)}
        </div>
      )}

      {ready && (
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn gold" onClick={render} disabled={busy}>Render video</button>
          <button className="btn" onClick={() => setId(null)}>Change options</button>
          <small className="muted">1920×1080 · 60 fps · H.264</small>
        </div>
      )}

      {rendering && (
        <div className="job-progress" data-testid="video-rendering">
          <div className="pbar" role="progressbar"><i style={{ width: `${p && p.total ? (p.done / p.total) * 100 : 3}%` }} /></div>
          <p>Rendering… {p && p.total ? `${Math.round((p.done / p.total) * 100)}%` : ''} · {eta(p?.eta_s)}</p>
          <button className="btn sm" onClick={cancel}>Cancel</button>
        </div>
      )}

      {done && v && (
        <div className="row" style={{ marginTop: 12 }} data-testid="video-done">
          <a className="btn gold" href={videoUrl(v.video!, true)} download data-testid="video-download">Download video</a>
          <span className="muted">{v.duration_s?.toFixed(0)} s · {v.size_mb} MB · rendered in {v.render_s?.toFixed(0)} s</span>
          {v.checks.map((c) => <small key={c.label} className={c.hash_ok === false ? 'err' : 'muted'}>{c.label}: {c.hash_ok ? 'replay matches the recorded run' : c.hash_ok === false ? 'REPLAY DIFFERS' : 'no recorded run to compare with'}</small>)}
        </div>
      )}

      {v && v.status === 'failed' && <p className="err" role="alert">The export failed: {v.error} <button className="btn sm" onClick={() => setId(null)}>Start over</button></p>}
      {v && v.status === 'cancelled' && <p className="muted">Cancelled. <button className="btn sm" onClick={() => setId(null)}>Start over</button></p>}
      {error && <p className="err" role="alert">{error}</p>}
    </section>
  )
}
