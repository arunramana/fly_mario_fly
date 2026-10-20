import { useEffect, useRef } from 'react'
import type { OverlayItem } from '../api/models'

const W = 256, H = 240
const K = 4 // overlay canvas pixels per NES pixel
const STATUS_BAR = 32 // level y has the 32 px status bar above it
const RIGHT_INSET = 22 / 4 // screen_right markers sit this far inside the right edge

const dash = (l: OverlayItem['line']): number[] => (l === 'dotted' ? [3, 7] : l === 'dashed' ? [14, 9] : [])

/** Overlay items are level pixels: subtract the frame's scroll_x. `screen_right` dots are pinned to the right edge. */
function drawOverlay(g: CanvasRenderingContext2D, items: OverlayItem[], scrollX: number) {
  g.clearRect(0, 0, W * K, H * K)
  const sx = (x: number) => (x - scrollX) * K
  const sy = (y: number) => (y + STATUS_BAR) * K
  for (const it of items) {
    const p = it.geometry
    g.strokeStyle = g.fillStyle = it.colour
    g.lineWidth = 3
    g.setLineDash(dash(it.line))
    g.beginPath()
    if (it.kind === 'box') {
      g.strokeRect(sx(p[0]), sy(p[1]), p[2] * K, p[3] * K)
    } else if (it.kind === 'line') {
      g.moveTo(sx(p[0]), sy(p[1])); g.lineTo(sx(p[2]), sy(p[3])); g.stroke()
    } else if (it.kind === 'dot') {
      const right = it.anchor === 'screen_right'
      g.globalAlpha = right ? 0.5 : 1
      g.arc(right ? (W - RIGHT_INSET) * K : sx(p[0]), sy(p[1]), Math.max(2, p[2] * K), 0, 2 * Math.PI)
      g.fill()
      g.globalAlpha = 1
    } else { // wedge: the cone from Mario's eye to the near face of the box it measures
      const [ex, ey, x, y, w, h] = p
      const near = x >= ex ? x : x + w
      g.moveTo(sx(ex), sy(ey)); g.lineTo(sx(near), sy(y)); g.lineTo(sx(near), sy(y + h)); g.closePath()
      g.globalAlpha = 0.07; g.fill(); g.globalAlpha = 1
      g.lineWidth = 1; g.stroke()
    }
  }
  g.setLineDash([])
}

/**
 * The game picture and the senses overlay are two canvases, so "Show senses" only flips the overlay's visibility
 * (it is always kept up to date underneath). The picture is the screen after the frame's action (`scroll_x_after`),
 * the overlay is read before it (`scroll_x`).
 */
export default function GameStage({ png, overlay, scrollX = 0, showOverlay, frozen }: {
  png?: string
  overlay?: OverlayItem[]
  scrollX?: number
  showOverlay: boolean
  frozen?: boolean
}) {
  const pic = useRef<HTMLCanvasElement>(null)
  const ov = useRef<HTMLCanvasElement>(null)
  const latest = useRef(0)

  useEffect(() => {
    const mine = ++latest.current
    const g = pic.current?.getContext('2d')
    if (!g) return
    if (!png) { g.fillStyle = '#000'; g.fillRect(0, 0, W, H); return }
    const img = new Image()
    img.onload = () => { if (mine === latest.current) g.drawImage(img, 0, 0) }
    img.src = `data:image/png;base64,${png}`
  }, [png])

  useEffect(() => {
    const g = ov.current?.getContext('2d')
    if (g) drawOverlay(g, overlay ?? [], scrollX)
  }, [overlay, scrollX])

  return (
    <div className={`stage ${frozen ? 'frozen' : ''}`}>
      <canvas ref={pic} width={W} height={H} data-testid="picture" aria-label="game picture" />
      <canvas ref={ov} width={W * K} height={H * K} className="overlay" data-testid="overlay"
        style={{ visibility: showOverlay ? 'visible' : 'hidden' }} />
    </div>
  )
}
