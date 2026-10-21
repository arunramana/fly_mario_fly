// The brain panel: index bars from the frame's light state (rate 0..1 per neuron group). The soma-position picture
// is still a placeholder (one dot per slot, lit by the group it stands for).
const dots = Array.from({ length: 140 }, (_, i) => ({
  x: 20 + ((i * 97) % 340), y: 16 + ((i * 53) % 208), g: i,
}))

export default function BrainPanel({ rates }: { rates: Record<string, number> }) {
  const names = Object.keys(rates).sort()
  return (
    <div data-testid="brain-panel">
      <div className="brain-panel">
        <svg viewBox="0 0 380 240" width="100%" height="100%">
          {dots.map((d) => {
            const r = names.length ? rates[names[d.g % names.length]] : 0
            return <circle key={d.g} cx={d.x} cy={d.y} r={2 + r * 3} fill={r > 0.5 ? '#F8B800' : '#5C94FC'} opacity={0.25 + r * 0.75} />
          })}
        </svg>
      </div>
      <div className="idx-list">
        {names.map((n) => (
          <div className="idx-row" key={n}>
            <span>{n}</span>
            <div className="bar"><i style={{ width: `${Math.round(rates[n] * 100)}%` }} /></div>
            <span className="muted">{Math.round(rates[n] * 100)}</span>
          </div>
        ))}
        {!names.length && <p className="muted">Waiting for the first frame…</p>}
      </div>
    </div>
  )
}
