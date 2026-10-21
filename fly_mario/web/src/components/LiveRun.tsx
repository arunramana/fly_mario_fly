import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { FrameEvent, RunResult, RunStream } from '../api/models'
import RunStage from './RunStage'

const SPEEDS: [number, string][] = [[1, '1×'], [100, 'Fast']]

/** A run being played, embedded in a page: the brain beside the game, a speed switch, and how it ended. Keyed by run id. */
export default function LiveRun({ runId }: { runId: string }) {
  const stream = useRef<RunStream | null>(null)
  const [frame, setFrame] = useState<FrameEvent | null>(null)
  const [brain, setBrain] = useState<string>()
  const [result, setResult] = useState<RunResult | null>(null)
  const [error, setError] = useState('')
  const [speed, setSpeed] = useState(1)

  useEffect(() => {
    // Connect after a tick: StrictMode mounts, unmounts and remounts at once, and a run connected to and dropped is aborted.
    let s: RunStream | undefined
    const t = setTimeout(() => {
      s = api.openRun(runId)
      stream.current = s
      s.onEvent((e) => {
        if (e.type === 'frame') { if (e.brain_jpg) setBrain(e.brain_jpg); setFrame(e) }
        else if (e.type === 'end') setResult(e.result)
        else if (e.type === 'error') setError(e.message)
      })
    }, 0)
    return () => { clearTimeout(t); s?.close() }
  }, [runId])

  const what = result?.death?.object_label ?? result?.death?.object_type ?? ''
  return (
    <div className="live-run" data-testid="live-run">
      <RunStage brain={brain} game={frame?.frame_png} overlay={frame?.overlay_png} at={frame?.overlay_at} showBrain showSenses />
      <div className="row" style={{ marginTop: 10 }}>
        <div className="speeds" role="group" aria-label="speed">
          {SPEEDS.map(([v, l]) => (
            <button key={v} className={`chip ${speed === v ? 'on' : ''}`} aria-pressed={speed === v}
              onClick={() => { setSpeed(v); stream.current?.setSpeed(v) }}>{l}</button>
          ))}
        </div>
        {result && (
          <span data-testid="live-run-end" className={result.outcome === 'flag' ? 'ok' : 'bad'}>
            {result.outcome === 'flag' ? 'Reached the flag' : result.outcome === 'died' ? `Died at x ${result.death?.x ?? Math.round(result.max_x)}${what ? ` · ${what}` : ''}` : `Ended (${result.outcome})`}
          </span>
        )}
        {error && <span className="err" role="alert">{error}</span>}
      </div>
    </div>
  )
}
