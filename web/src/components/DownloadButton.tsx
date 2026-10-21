import { useEffect, useRef, useState } from 'react'
import { api, videoUrl } from '../api/client'
import type { VideoRequest, VideoSummary } from '../api/models'
import { errText } from '../hooks'
import { eta, isLive, useVideo } from '../jobs'
import { FEATURES } from '../features'

/** Hand the browser the mp4: the server sends it as an attachment, so it is saved, not played. */
function saveFile(path: string) {
  const a = document.createElement('a')
  a.href = videoUrl(path, true)
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

/** One button: it renders the video in the background (a progress bar shows how far), then the browser saves the mp4.
 *  With `readyPath` (already rendered) it saves straight away. `onDone` gets the finished export (to play it in the page). */
export default function DownloadButton({ label, build, disabled, title, readyPath, onDone }: {
  label: string
  build: () => VideoRequest
  disabled?: boolean
  title?: string
  readyPath?: string | null
  onDone?: (v: VideoSummary) => void
}) {
  const [id, setId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const video = useVideo(id)
  const v = video.data
  const handled = useRef<string | null>(null)
  const done = useRef(onDone)
  useEffect(() => { done.current = onDone })

  useEffect(() => {
    if (v && v.status === 'finished' && v.video && handled.current !== v.id) {
      handled.current = v.id
      saveFile(v.video)
      done.current?.(v)
    }
  }, [v])

  if (!FEATURES.downloads) return null
  const working = !!v && isLive(v.status) && !error
  const p = v?.progress
  const start = async () => {
    setError('')
    if (readyPath) { saveFile(readyPath); return }
    try { setId((await api.startVideo(build())).id) } catch (e) { setError(errText(e)) }
  }
  const cancel = async () => { if (id) { await api.cancelVideo(id); await video.refetch() } }

  return (
    <span className="download" data-testid="download" data-status={v?.status ?? ''}>
      <button className="btn" onClick={start} disabled={disabled || working} title={title}>{working ? 'Rendering…' : label}</button>
      {working && (
        <span className="download-progress" data-testid="download-progress">
          <span className="pbar" role="progressbar"><i style={{ width: `${p && p.total ? (p.done / p.total) * 100 : 3}%` }} /></span>
          <small>{p && p.total ? `${Math.round((p.done / p.total) * 100)}% · ` : ''}{eta(p?.eta_s)}</small>
          <button className="btn sm" onClick={cancel}>Cancel</button>
        </span>
      )}
      {v?.status === 'finished' && v.video && (
        <small className="muted" data-testid="download-done">Saved {v.size_mb} MB · <a href={videoUrl(v.video, true)}>download again</a></small>
      )}
      {v?.status === 'failed' && <small className="err" role="alert">Failed: {v.error}</small>}
      {error && <small className="err" role="alert">{error}</small>}
    </span>
  )
}
