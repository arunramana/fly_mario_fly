import type { OverlayItem } from '../api/models'

/** The game at x4: the canvas the overlay is drawn on (the same size the server's pictures used to be). */
export const GAME_W = 1024, GAME_H = 960
const DASH: Record<string, number[]> = { solid: [], dashed: [14, 9], dotted: [3, 7] } // [on, off] px, as render.draw

const sx = (wx: number, scroll: number) => (wx - scroll) * 4
const sy = (ly: number) => (ly + 32) * 4 // level y has the 32 px status bar above it

function seg(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, width: number, style: string) {
  ctx.lineWidth = width
  ctx.setLineDash(DASH[style] ?? [])
  ctx.beginPath()
  ctx.moveTo(x0, y0)
  ctx.lineTo(x1, y1)
  ctx.stroke()
}

/** Draw the senses' overlay items (level pixels) for a screen scrolled to `scroll` onto a 1024 x 960 canvas: boxes,
 *  lines, dots, the cone ("wedge") from Mario's eye to the box it measures, and the half-transparent direction marker
 *  ("screen_right"). Same colours, widths and line styles as render.draw.game_panel. Cones go first, as a faint fill. */
export function drawOverlay(ctx: CanvasRenderingContext2D, items: readonly OverlayItem[], scroll: number): void {
  ctx.clearRect(0, 0, GAME_W, GAME_H)
  ctx.lineCap = 'butt'
  const ordered = [...items].sort((a, b) => Number(a.kind !== 'wedge') - Number(b.kind !== 'wedge'))
  for (const it of ordered) {
    const g = it.geometry
    ctx.strokeStyle = ctx.fillStyle = it.colour
    if (it.kind === 'box') {
      const [x, y, w, h] = g
      const c = [[sx(x, scroll), sy(y)], [sx(x + w, scroll), sy(y)], [sx(x + w, scroll), sy(y + h)], [sx(x, scroll), sy(y + h)]]
      for (let i = 0; i < 4; i++) seg(ctx, c[i][0], c[i][1], c[(i + 1) % 4][0], c[(i + 1) % 4][1], 3, it.line)
    } else if (it.kind === 'line') {
      seg(ctx, sx(g[0], scroll), sy(g[1]), sx(g[2], scroll), sy(g[3]), 3, it.line)
    } else if (it.kind === 'dot') {
      const rad = Math.max(2, Math.round(g[2] * 4))
      const screenRight = it.anchor === 'screen_right' // a direction marker, 22 px inside the edge, half transparent
      ctx.globalAlpha = screenRight ? 0.5 : 1
      ctx.setLineDash([])
      ctx.beginPath()
      ctx.arc(screenRight ? GAME_W - 22 : sx(g[0], scroll), sy(g[1]), rad, 0, Math.PI * 2)
      ctx.fill()
      ctx.globalAlpha = 1
    } else if (it.kind === 'wedge') {
      const [ex, ey, x, y, w, h] = g
      const near = x >= ex ? x : x + w
      const eye = [sx(ex, scroll), sy(ey)], top = [sx(near, scroll), sy(y)], bot = [sx(near, scroll), sy(y + h)]
      ctx.globalAlpha = 0.07
      ctx.setLineDash([])
      ctx.beginPath()
      ctx.moveTo(eye[0], eye[1]); ctx.lineTo(top[0], top[1]); ctx.lineTo(bot[0], bot[1]); ctx.closePath()
      ctx.fill()
      ctx.globalAlpha = 1
      seg(ctx, eye[0], eye[1], top[0], top[1], 1, it.line)
      seg(ctx, eye[0], eye[1], bot[0], bot[1], 1, it.line)
    }
  }
  ctx.setLineDash([])
}
