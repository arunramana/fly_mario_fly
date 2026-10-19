import type { Box, ObjectInstance, OverlayItem } from '../api/types'

const W = 256, H = 240
const dash = (l: OverlayItem['line']) => (l === 'dotted' ? '2 3' : l === 'dashed' ? '8 4' : undefined)

/** Placeholder game picture (plain shapes; real frames come with the backend) plus an overlay layer. */
export default function GameStage({ mario, objects, overlay, showOverlay, frozen }: {
  mario?: Box
  objects?: ObjectInstance[]
  overlay?: OverlayItem[]
  showOverlay: boolean
  frozen?: boolean
}) {
  const m = mario ?? { x: 60, y: 192, w: 14, h: 16 }
  return (
    <div className={`stage ${frozen ? 'frozen' : ''}`}>
      <svg viewBox={`0 0 ${W} ${H}`} shapeRendering="crispEdges" role="img" aria-label="game frame placeholder">
        <rect width={W} height={H} fill="#5c94fc" />
        <rect y={208} width={W} height={32} fill="#b84c00" />
        <rect y={208} width={W} height={4} fill="#000" />
        {(objects ?? []).map((o) => (
          <rect key={o.id} x={o.box.x} y={o.box.y} width={o.box.w} height={o.box.h}
            fill={o.type === 'pipe' ? '#00a800' : '#a0522d'} stroke="#000" strokeWidth={1} />
        ))}
        <rect x={m.x} y={m.y} width={m.w} height={m.h} fill="#f83800" stroke="#000" strokeWidth={1} />
      </svg>
      {showOverlay && (
        <svg className="overlay" viewBox={`0 0 ${W} ${H}`} data-testid="overlay">
          {(overlay ?? []).map((it, i) => {
            const g = it.geometry
            const common = { stroke: it.colour, strokeWidth: 1.5, strokeDasharray: dash(it.line), fill: 'none' }
            if (it.kind === 'box') return <rect key={i} x={g[0] - 2} y={g[1] - 2} width={g[2] + 4} height={g[3] + 4} {...common} />
            if (it.kind === 'line') return <line key={i} x1={g[0]} y1={g[1]} x2={g[2]} y2={g[3]} {...common} />
            if (it.kind === 'dot') return <circle key={i} cx={g[0]} cy={g[1]} r={g[2]} fill={it.colour} />
            return <polygon key={i} points={g.join(',')} {...common} />
          })}
        </svg>
      )}
    </div>
  )
}
