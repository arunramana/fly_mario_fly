import type { CSSProperties } from 'react'
import type { Fly, KnobUI } from '../api/models'

// Sliders carry a position 0..1 and are shown with word labels only; no number reaches the screen.
// A switch knob (kind 'switch') is the same position pinned to 0 or 1, shown as two labelled buttons.

/** One slider. `showReset` adds the little Reset button of the Advanced drawer. */
export function KnobSlider({ knob, fly, onChange, showReset = false, compact = false, baseline, original = false }: {
  knob: KnobUI
  fly: Fly
  onChange: (fly: Fly) => void
  showReset?: boolean
  compact?: boolean
  /** The position the slider is compared with for "changed" (default: the knob's own default). */
  baseline?: number
  /** Show the hand-set original dials instead of the fly's own: every slider sits at its tick and cannot move. */
  original?: boolean
}) {
  const set = original ? undefined : fly.knobs[knob.key]
  const pos = set ?? knob.position
  const changed = set !== undefined && Math.abs(set - (baseline ?? knob.position)) > 0.0005
  const tuned = !!fly.dials?.[knob.key]?.tuned
  const reset = () => {
    const rest = { ...fly.knobs }
    delete rest[knob.key]
    onChange({ ...fly, knobs: rest })
  }
  const setPos = (p: number) => onChange({ ...fly, knobs: { ...fly.knobs, [knob.key]: p } })
  return (
    <div className={`knob ${knob.origin}`} data-tuned={tuned}>
      <div className="knob-top">
        <span className="knob-name">
          {!compact && <i className={knob.evolvable ? 'evo' : ''} />}
          {knob.label}{tuned && <span className="tuned-mark" title="Evolution moved this knob"> · tuned</span>}{compact && changed && <span className="changed"> · changed</span>}
        </span>
        {showReset && <button className="reset" disabled={original || !changed} onClick={reset}>Reset to original</button>}
      </div>
      {knob.kind === 'switch' ? (
        <div className="switch" role="group" aria-label={knob.label}>
          <button className={pos < 0.5 ? 'on' : ''} aria-pressed={pos < 0.5} disabled={original} onClick={() => setPos(0)}>{knob.lo_label}</button>
          <button className={pos >= 0.5 ? 'on' : ''} aria-pressed={pos >= 0.5} disabled={original} onClick={() => setPos(1)}>{knob.hi_label}</button>
        </div>
      ) : (<>
      <div className="track" style={{ '--tick': `${knob.position * 100}%` } as CSSProperties}>
      <input
        type="range" min={0} max={1000} aria-label={knob.label} disabled={original} style={{ '--fill': `${pos * 100}%` } as CSSProperties}
        value={Math.round(pos * 1000)}
        onChange={(e) => onChange({ ...fly, knobs: { ...fly.knobs, [knob.key]: Number(e.target.value) / 1000 } })}
      />
      <i className="tick" data-testid="original-tick" title="original" />
      </div>
      <div className="ends"><span>{knob.lo_label}</span><span>{knob.hi_label}</span></div>
      </>)}
    </div>
  )
}

export interface KnobSection { key: string; title: string; colour: string; knobs: KnobUI[] }

/** The "Fine-tune this fly" drawer: only the senses and actions that are on appear, each with its sliders. */
export function AdvancedDrawer({ sections, fly, original = false, onChange, onClose, onRun, running }: {
  sections: KnobSection[]
  fly: Fly
  original?: boolean
  onChange: (fly: Fly) => void
  onClose: () => void
  onRun: () => void
  running: boolean
}) {
  return (
    <aside className="drawer" role="dialog" aria-label="Fine-tune this fly">
      <div className="drawer-top">
        <h2 className="title">Fine-tune this fly</h2>
        <button className="x" onClick={onClose} aria-label="close">×</button>
      </div>
      <p className="lead">Only the senses that are on appear here. Drag to feel the difference, then press Run. The exact values are saved with the fly. The small tick on each slider is where the original, hand-set dial sits.{original ? ' Original dials are on, so the sliders are locked: switch to Tuned to move them.' : ''}</p>
      <div className="dkey">
        <span><i className="fly" />from the fly</span><span><i className="invented" />invented</span><span><i className="evo" />tuned by evolution</span><span><i className="tick" />original</span>
      </div>
      <div className="drawer-body">
        {sections.length ? sections.map((s) => (
          <section className="dsec" key={s.key}>
            <h3 style={{ '--c': s.colour } as CSSProperties}><i />{s.title}</h3>
            {s.knobs.map((k) => <KnobSlider key={k.key} knob={k} fly={fly} onChange={onChange} showReset original={original} />)}
          </section>
        )) : <p className="muted">Switch something on to tune it.</p>}
      </div>
      <div className="drawer-foot">
        <button className="btn" disabled={original} onClick={() => onChange({ ...fly, knobs: {} })}>Reset all to original</button>
        <button className="btn gold big" onClick={onRun} disabled={running}>▶ Run with these</button>
      </div>
    </aside>
  )
}
