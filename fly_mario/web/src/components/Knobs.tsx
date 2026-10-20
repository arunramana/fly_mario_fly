import type { Fly, KnobUI } from '../api/models'

// Sliders carry a position 0..1 and are shown with word labels only; no number reaches the screen.
export function OriginKey() {
  return (
    <div className="origin-key muted">
      <span className="t">■ from the fly</span><span className="o">■ invented</span>
    </div>
  )
}

export default function Knobs({ knobs, fly, onChange }: {
  knobs: KnobUI[]
  fly: Fly
  onChange: (fly: Fly) => void
}) {
  return (
    <div className="drawer-body">
      {knobs.map((k) => (
        <div key={k.key} className={`knob ${k.origin}`}>
          <div className="name">{k.label}</div>
          <input
            type="range" min={0} max={1000} aria-label={k.label}
            value={Math.round((fly.knobs[k.key] ?? k.position) * 1000)}
            onChange={(e) => onChange({ ...fly, knobs: { ...fly.knobs, [k.key]: Number(e.target.value) / 1000 } })}
          />
          <div className="ends"><span>{k.lo_label}</span><span>{k.hi_label}</span></div>
        </div>
      ))}
    </div>
  )
}
