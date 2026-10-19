import type { FlyConfig, KnobSpec } from '../api/types'

// Sliders are shown with word labels only; the number never reaches the screen.
const toPos = (k: KnobSpec, v: number) =>
  k.scale === 'log' ? (Math.log(v) - Math.log(k.lo)) / (Math.log(k.hi) - Math.log(k.lo)) : (v - k.lo) / (k.hi - k.lo)
const fromPos = (k: KnobSpec, p: number) =>
  k.scale === 'log' ? Math.exp(Math.log(k.lo) + p * (Math.log(k.hi) - Math.log(k.lo))) : k.lo + p * (k.hi - k.lo)

export function OriginKey() {
  return (
    <div className="origin-key muted">
      <span className="t">■ from the fly</span><span className="o">■ invented</span>
    </div>
  )
}

export default function Knobs({ knobs, fly, onChange }: {
  knobs: KnobSpec[]
  fly: FlyConfig
  onChange: (fly: FlyConfig) => void
}) {
  return (
    <div className="drawer-body">
      {knobs.map((k) => {
        const v = fly.knobs[k.key] ?? k.default
        return (
          <div key={k.key} className={`knob ${k.origin}`}>
            <div className="name">{k.label}</div>
            <input
              type="range" min={0} max={1000} aria-label={k.label}
              value={Math.round(toPos(k, v) * 1000)}
              onChange={(e) => onChange({ ...fly, knobs: { ...fly.knobs, [k.key]: fromPos(k, Number(e.target.value) / 1000) } })}
            />
            <div className="ends"><span>{k.lo_label}</span><span>{k.hi_label}</span></div>
          </div>
        )
      })}
    </div>
  )
}
