import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { FrameEvent, MomentSummary, RunResult, RunStream } from '../api/models'
import BrainPanel from '../components/BrainPanel'
import GameStage from '../components/GameStage'
import { momentPictures } from '../state'

const SPEEDS: [number, string][] = [[0.25, '0.25x'], [0.5, '0.5x'], [1, '1x'], [2, '2x'], [4, '4x'], [100, 'max']]
const KEEP_PICTURES = 2400 // frames of pictures kept (a few MB) so a moment, even an old one, still has its picture

export default function RunScreen() {
  const { runId = '' } = useParams()
  const nav = useNavigate()
  const stream = useRef<RunStream | null>(null)
  const pictures = useRef(new Map<number, string>())
  const lastFrame = useRef(0)
  const [diedAt, setDiedAt] = useState<number | null>(null)
  const [frame, setFrame] = useState<FrameEvent | null>(null)
  const [moments, setMoments] = useState<MomentSummary[]>([])
  const [result, setResult] = useState<RunResult | null>(null)
  const [error, setError] = useState('')
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [showSenses, setShowSenses] = useState(true)
  const [showBrain, setShowBrain] = useState(true)
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })

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
          keep.set(e.frame, e.frame_png)
          keep.delete(e.frame - KEEP_PICTURES)
          lastFrame.current = e.frame
          setFrame(e)
        } else if (e.type === 'moment') {
          remember(e.moment)
          setMoments((m) => (m.some((x) => x.id === e.moment.id) ? m : [...m, e.moment]))
        } else if (e.type === 'end') {
          setResult(e.result)
          if (e.result.outcome === 'died') setDiedAt(lastFrame.current)
        }
        else if (e.type === 'error') setError(e.message)
        else { setPaused(e.paused); setSpeed(e.speed) }
      })
    }, 0)
    return () => { clearTimeout(t); s?.close() }
  }, [runId])

  const total = frame?.total ?? 1
  const pct = (f: number) => `${(f / total) * 100}%`
  const togglePause = () => {
    if (paused) stream.current?.play(); else stream.current?.pause()
    setPaused(!paused)
  }
  const saveHere = async () => {
    if (!frame) return
    const m = await api.saveMoment(runId, `Moment at frame ${frame.frame}`)
    setMoments((x) => (x.some((y) => y.id === m.id) ? x : [...x, m]))
    const png = pictures.current.get(m.frame) ?? frame.frame_png
    momentPictures.set(m.id, png)
  }
  const rewind = async () => {
    const known = moments.find((m) => m.kind === 'death') ?? (await api.getRunMoments(runId)).find((m) => m.kind === 'death')
    if (known) nav(`/moment/${encodeURIComponent(known.id)}`)
    else setError('There is no "3 s before death" moment for this run.')
  }

  const label = (name: string) => registry.data?.objects.find((o) => o.name === name)?.label ?? name
  const cause = (c: string) => {
    if (c.startsWith('enemy:')) return `Touched a ${label(c.slice(6))}`
    return c === 'pit' ? 'Fell in a pit' : 'Died'
  }

  return (
    <>
      {error && <div className="banner died" role="alert"><p>{error}</p></div>}
      {result && (
        <div className={`banner ${result.outcome === 'flag' ? 'flag' : 'died'}`} role="status" data-outcome={result.outcome}>
          {result.outcome === 'flag' ? (
            <>
              <h2>FLAG REACHED!</h2>
              <p>Score {result.score} · got as far as {Math.round(result.max_x)} px</p>
            </>
          ) : (
            <>
              <h2>{result.outcome === 'died' ? 'THE FLY DIED' : `THE RUN ENDED (${result.outcome})`}</h2>
              <p>{result.outcome === 'died' ? cause(String(result.death?.cause ?? '')) : result.outcome} · got as far as {Math.round(result.max_x)} px</p>
            </>
          )}
          <div className="row">
            {result.outcome === 'died' && <button className="gold" onClick={rewind}>Rewind 3 s &amp; change the fly</button>}
            {result.parent_moment && (
              <button onClick={() => nav(`/moment/${encodeURIComponent(result.parent_moment!)}`)}>Back to the moment</button>
            )}
          </div>
        </div>
      )}

      <div className="run-layout">
        {showBrain && (
          <section className="box">
            <h3>Brain</h3>
            <BrainPanel rates={frame?.rates ?? {}} />
          </section>
        )}

        <section style={showBrain ? undefined : { gridColumn: '1 / -1' }}>
          <GameStage png={frame?.frame_png} overlay={frame?.overlay} scrollX={frame?.scroll_x} showOverlay={showSenses} />
          <div className="row" style={{ marginTop: 12 }}>
            <label className="check"><input type="checkbox" checked={showSenses} onChange={(e) => setShowSenses(e.target.checked)} />Show senses</label>
            <label className="check"><input type="checkbox" checked={showBrain} onChange={(e) => setShowBrain(e.target.checked)} />Show brain</label>
          </div>

          <div className="timeline" data-testid="timeline">
            <div className="fill" style={{ width: pct(frame?.frame ?? 0) }} />
            {moments.map((m) => <div key={m.id} className="moment" title={m.name} data-testid="moment-mark" style={{ left: pct(m.frame) }} />)}
            {diedAt != null && <div className="death" title="death" data-testid="death-mark" style={{ left: pct(diedAt) }} />}
          </div>

          <div className="row spread">
            <div className="row">
              <button className="tool" onClick={togglePause} aria-label="pause">{paused ? '▶' : '⏸'}</button>
              <button className="tool" onClick={() => { setPaused(true); stream.current?.step() }} aria-label="step">⏭</button>
              <select aria-label="speed" value={speed} onChange={(e) => { const v = Number(e.target.value); setSpeed(v); stream.current?.setSpeed(v) }}>
                {SPEEDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <span className="muted">frame {frame?.frame ?? 0}</span>
            </div>
            <button className="gold" onClick={saveHere} disabled={!!result || !frame}>Save this moment</button>
          </div>
        </section>
      </div>
    </>
  )
}
