import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { FrameEvent, MomentSummary, RunResult, RunStream } from '../api/models'
import RunStage from '../components/RunStage'
import { errText, useStartRun } from '../hooks'
import { momentPictures, runRequests, useDraft, type Picture } from '../draft'

const SPEEDS: [number, string][] = [[0.5, '0.5×'], [1, '1×'], [100, 'Fast']]
// Only a recent window of pictures is kept: a moment picture is copied out of it when the moment arrives, and the
// "3 s before death" moment (180 frames back, on a 30-frame snapshot ring) is always inside it.
const KEEP_PICTURES = 300

/** Keyed by run id: a restart opens a fresh screen instead of resetting this one. */
export default function RunScreen() {
  const { runId = '' } = useParams()
  return <RunView key={runId} runId={runId} />
}

function RunView({ runId }: { runId: string }) {
  const nav = useNavigate()
  const { scene, fly } = useDraft()
  const stream = useRef<RunStream | null>(null)
  const pictures = useRef(new Map<number, Picture>())
  const lastFrame = useRef(0)
  const [diedAt, setDiedAt] = useState<number | null>(null)
  const [frame, setFrame] = useState<FrameEvent | null>(null)
  const [brain, setBrain] = useState<string>()
  const [moments, setMoments] = useState<MomentSummary[]>([])
  const [result, setResult] = useState<RunResult | null>(null)
  const [error, setError] = useState('')
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [showSenses, setShowSenses] = useState(true)
  const [showBrain, setShowBrain] = useState(true)
  const restart = useStartRun()

  useEffect(() => {
    const keep = pictures.current
    // The picture of a moment: its own frame, else the nearest earlier one still kept.
    const remember = (m: MomentSummary) => {
      let at = -1
      for (const f of keep.keys()) if (f <= m.frame && f > at) at = f
      const p = keep.get(at)
      if (p) momentPictures.set(m.id, p)
    }
    // Connect after a tick: React StrictMode mounts, unmounts and remounts at once in dev, and a run that has been
    // connected to and dropped is aborted by the server.
    let s: RunStream | undefined
    const t = setTimeout(() => {
      s = api.openRun(runId)
      stream.current = s
      s.onEvent((e) => {
        if (e.type === 'frame') {
          keep.set(e.frame, { game: e.frame_png, overlay: e.overlay_png, at: e.overlay_at })
          keep.delete(e.frame - KEEP_PICTURES)
          lastFrame.current = e.frame
          if (e.brain_jpg) setBrain(e.brain_jpg)
          setFrame(e)
        } else if (e.type === 'moment') {
          remember(e.moment)
          setMoments((m) => (m.some((x) => x.id === e.moment.id) ? m : [...m, e.moment]))
        } else if (e.type === 'end') {
          setResult(e.result)
          if (e.result.outcome === 'died') setDiedAt(lastFrame.current)
        } else if (e.type === 'error') setError(e.message)
        else { setPaused(e.paused); setSpeed(e.speed) }
      })
    }, 0)
    return () => { clearTimeout(t); s?.close() }
  }, [runId])

  const total = Math.max(frame?.frame ?? 1, 1) // the bar is the run so far: its end is now
  const pct = (f: number) => `${Math.min(100, (f / total) * 100)}%`
  const togglePause = () => {
    if (paused) stream.current?.play(); else stream.current?.pause()
    setPaused(!paused)
  }
  const saveHere = async () => {
    if (!frame) return
    try {
      const m = await api.saveMoment(runId, `Moment at frame ${frame.frame}`)
      setMoments((x) => (x.some((y) => y.id === m.id) ? x : [...x, m]))
      momentPictures.set(m.id, pictures.current.get(m.frame) ?? { game: frame.frame_png, overlay: frame.overlay_png, at: frame.overlay_at })
    } catch (e) { setError(errText(e)) }
  }
  const rewind = async () => {
    const known = moments.find((m) => m.kind === 'death') ?? (await api.getRunMoments(runId)).find((m) => m.kind === 'death')
    if (known) nav(`/moment/${encodeURIComponent(known.id)}`)
    else setError('There is no "3 s before death" moment for this run.')
  }
  // Restart: the same fly on the same scene, from the same start (a run that was resumed from a moment resumes again).
  const again = () => {
    const req = runRequests.get(runId)?.req ?? { fly, scene, from_moment: result?.parent_moment ?? null }
    restart.mutate(req)
  }

  const death = result?.death
  const what = death?.object_label ?? death?.object_type ?? ''
  const x = (result?.max_x ?? 0).toFixed(0)
  const dials = result?.dials ?? runRequests.get(runId)?.req.dials ?? 'tuned'

  return (
    <div className="run">
      <RunStage brain={brain} game={frame?.frame_png} overlay={frame?.overlay_png} at={frame?.overlay_at}
        showBrain={showBrain} showSenses={showSenses} />

      <div className="toolrow">
        <label className="check"><input type="checkbox" checked={showSenses} onChange={(e) => setShowSenses(e.target.checked)} />Show senses (boxes, lines, dots)</label>
        <label className="check"><input type="checkbox" checked={showBrain} onChange={(e) => setShowBrain(e.target.checked)} />Show brain</label>
      </div>

      <div className="toolrow" style={{ flexWrap: 'nowrap' }}>
        <div className="transport">
          <button className="tbtn" onClick={again} disabled={restart.isPending} aria-label="restart" title="Restart: the same fly on the same scene">⏮</button>
          <button className="tbtn play" onClick={togglePause} disabled={!!result} aria-label="pause" title={paused ? 'Play' : 'Pause'}>{paused ? '▶' : '❚❚'}</button>
          <button className="tbtn" onClick={() => { setPaused(true); stream.current?.step() }} disabled={!!result} aria-label="step" title="One frame">⏭</button>
        </div>
        <div className="timeline" data-testid="timeline" aria-label={`frame ${frame?.frame ?? 0}`}>
          <div className="fill" style={{ width: '100%' }} />
          {moments.map((m) => <div key={m.id} className="mk" title={m.name} data-testid="moment-mark" style={{ left: pct(m.frame) }} />)}
          {diedAt != null && <div className="mk death" title="death" data-testid="death-mark" style={{ left: pct(diedAt) }} />}
        </div>
        <button className="btn" onClick={saveHere} disabled={!!result || !frame}>◆ Save this moment</button>
        <div className="speeds" role="group" aria-label="speed">
          {SPEEDS.map(([v, l]) => (
            <button key={v} className={`chip ${speed === v ? 'on' : ''}`} aria-pressed={speed === v}
              onClick={() => { setSpeed(v); stream.current?.setSpeed(v) }}>{l}</button>
          ))}
        </div>
      </div>

      {error && <div className="banner died" role="alert"><div><b>Something went wrong</b><p>{error}</p></div></div>}
      {result && (
        <div className={`banner ${result.outcome === 'flag' ? 'flag' : result.outcome === 'died' ? 'died' : 'info'}`} role="status" data-outcome={result.outcome} data-dials={dials}>
          <div>
            <small className="dials-note">Dials: {dials === 'original' ? 'Original' : 'Tuned'}</small>
            {result.outcome === 'flag' && <><b>Reached the flag!</b><p>Score {result.score} · got as far as x {x}</p></>}
            {result.outcome === 'died' && <><b>Died at x {death?.x ?? x}{what ? ` · ${what}` : ''}</b>
              <p>{death?.kind === 'enemy' ? `Touched a ${what}` : death?.kind === 'fall' ? `Fell in (${what})` : 'The fly died'} · score {result.score}</p></>}
            {result.outcome !== 'flag' && result.outcome !== 'died' && <><b>The run ended ({result.outcome}) at x {x}</b><p>Score {result.score}</p></>}
          </div>
          <div className="row">
            {result.outcome === 'died' && <button className="btn gold" onClick={rewind}>⏪ Rewind 3 s &amp; change the fly</button>}
            {result.parent_moment && (
              <button className="btn" onClick={() => nav(`/moment/${encodeURIComponent(result.parent_moment!)}`)}>Back to the moment</button>
            )}
            <button className="btn" onClick={again} disabled={restart.isPending}>Restart</button>
          </div>
        </div>
      )}
      {restart.isError && <p className="err" role="alert">{errText(restart.error)}</p>}
    </div>
  )
}
