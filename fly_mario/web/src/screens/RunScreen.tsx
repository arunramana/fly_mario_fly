import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { FrameEvent, MomentSummary, RunResult, RunStream } from '../api/types'
import BrainPanel from '../components/BrainPanel'
import GameStage from '../components/GameStage'

const SPEEDS = [0.25, 0.5, 1, 2, 4]
const REWIND_FRAMES = 180 // 3 s at 60 fps

export default function RunScreen() {
  const { runId = '' } = useParams()
  const nav = useNavigate()
  const stream = useRef<RunStream | null>(null)
  const [frame, setFrame] = useState<FrameEvent | null>(null)
  const [moments, setMoments] = useState<MomentSummary[]>([])
  const [result, setResult] = useState<RunResult | null>(null)
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [showSenses, setShowSenses] = useState(true)
  const [showBrain, setShowBrain] = useState(true)

  useEffect(() => {
    const s = api.runStream(runId)
    stream.current = s
    s.onEvent((e) => {
      if (e.type === 'frame') setFrame(e)
      else if (e.type === 'moment') setMoments((m) => [...m, e.moment])
      else setResult(e.result)
    })
    return () => s.close()
  }, [runId])

  const total = frame?.total ?? 1
  const pct = (f: number) => `${(f / total) * 100}%`
  const togglePause = () => {
    if (paused) stream.current?.play(); else stream.current?.pause()
    setPaused(!paused)
  }
  const restart = () => { setResult(null); setMoments([]); setPaused(false); stream.current?.restart() }
  const saveHere = async () => {
    if (!frame) return
    const m = await api.saveMoment(runId, frame.frame, `Moment at frame ${frame.frame}`)
    setMoments((x) => [...x, m])
  }
  const rewind = async () => {
    const at = Math.max(0, (result?.death?.frame ?? frame?.frame ?? 0) - REWIND_FRAMES)
    const m = await api.saveMoment(runId, at, 'Before the death', true)
    nav(`/moment/${m.id}`)
  }

  return (
    <>
      {result && (
        <div className={`banner ${result.outcome === 'flag' ? 'flag' : 'died'}`} role="status">
          {result.outcome === 'flag' ? (
            <>
              <h2>FLAG REACHED!</h2>
              <p>Score {result.score} · {result.counts.jumps ?? 0} jumps</p>
            </>
          ) : (
            <>
              <h2>THE FLY DIED</h2>
              <p>{result.death?.cause ?? result.outcome} · got as far as {Math.round(result.max_x)} px</p>
              <button className="gold" onClick={rewind}>Rewind 3 s &amp; change the fly</button>
            </>
          )}
        </div>
      )}

      <div className="run-layout">
        <section className="box">
          <h3>Brain</h3>
          {showBrain ? <BrainPanel rates={frame?.rates ?? {}} /> : <p className="muted">Brain hidden.</p>}
        </section>

        <section>
          <GameStage mario={frame?.mario} objects={frame?.objects} overlay={frame?.overlay} showOverlay={showSenses} />
          <div className="row" style={{ marginTop: 12 }}>
            <label className="check"><input type="checkbox" checked={showSenses} onChange={(e) => setShowSenses(e.target.checked)} />Show senses</label>
            <label className="check"><input type="checkbox" checked={showBrain} onChange={(e) => setShowBrain(e.target.checked)} />Show brain</label>
          </div>

          <div className="timeline" onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect()
            void ((e.clientX - r.left) / r.width) // seeking arrives with the real backend
          }}>
            <div className="fill" style={{ width: pct(frame?.frame ?? 0) }} />
            {moments.map((m) => <div key={m.id} className="moment" title={m.name} style={{ left: pct(m.frame) }} />)}
            {result?.death?.frame != null && <div className="death" title="death" style={{ left: pct(result.death.frame) }} />}
          </div>

          <div className="row spread">
            <div className="row">
              <button className="tool" onClick={restart} aria-label="restart">⏮</button>
              <button className="tool" onClick={togglePause} aria-label="pause">{paused ? '▶' : '⏸'}</button>
              <button className="tool" onClick={() => { setPaused(true); stream.current?.step() }} aria-label="step">⏭</button>
              <select aria-label="speed" value={speed} onChange={(e) => { const v = Number(e.target.value); setSpeed(v); stream.current?.setSpeed(v) }}>
                {SPEEDS.map((s) => <option key={s} value={s}>{s}x</option>)}
              </select>
              <span className="muted">frame {frame?.frame ?? 0}</span>
            </div>
            <button className="gold" onClick={saveHere}>Save this moment</button>
          </div>
        </section>
      </div>
    </>
  )
}
