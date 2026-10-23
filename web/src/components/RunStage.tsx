import { useEffect, useMemo, useRef } from 'react'
import type { OverlayItem } from '../api/models'
import { drawOverlay, GAME_H, GAME_W } from './overlayDraw'

/** A base64 picture as an object URL that is revoked once it has been replaced (a short while later, so the new picture
 *  has been swapped in first): a live run shows ~60 pictures a second, and each data: URL would stay in the browser's cache. */
function useBlobUrl(b64: string | null | undefined, type: string): string | undefined {
  const url = useMemo(() => {
    if (!b64) return undefined
    return URL.createObjectURL(new Blob([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], { type }))
  }, [b64, type])
  useEffect(() => () => { if (url) setTimeout(() => URL.revokeObjectURL(url), 1000) }, [url])
  return url
}

/** The senses' overlay: a transparent canvas over the game box, drawn in the browser from the overlay items (level pixels)
 *  and the screen's scroll. "Show senses" only flips its visibility. */
export function Overlay({ items, scrollX, visible }: { items?: readonly OverlayItem[] | null; scrollX?: number; visible: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const any = !!items && items.length > 0
  useEffect(() => {
    const ctx = ref.current?.getContext('2d')
    if (ctx) drawOverlay(ctx, items ?? [], scrollX ?? 0)
  }, [items, scrollX])
  return <canvas ref={ref} className="ov" data-testid="overlay" width={GAME_W} height={GAME_H}
    style={{ visibility: visible && any ? 'visible' : 'hidden' }} />
}

/**
 * The picture of a run, 1920 x 1080 like the videos: the R3 brain panel on the left, the NES screen at x4 on the right with
 * the senses overlay on top. Three separate layers, so "Show senses" and "Show brain" are only a visibility flip: nothing
 * is re-rendered. Without the brain the game slides to the middle, as in the videos made with --no-brain.
 */
export default function RunStage({ brain, game, overlay, scrollX, showBrain, showSenses, frozen }: {
  brain?: string
  game?: string
  overlay?: readonly OverlayItem[] | null
  scrollX?: number
  showBrain: boolean
  showSenses: boolean
  frozen?: boolean
}) {
  const brainUrl = useBlobUrl(brain, 'image/jpeg')
  const gameUrl = useBlobUrl(game, 'image/png')
  return (
    <div className={`stage ${showBrain ? '' : 'nobrain'} ${frozen ? 'frozen' : ''}`} data-testid="stage">
      {brainUrl && <img className="brain" data-testid="brain-panel" alt="the fly's brain, neurons lit by activity" src={brainUrl} />}
      <div className="game">
        {gameUrl && <img className="pic" data-testid="picture" alt="the game" src={gameUrl} />}
        <Overlay items={overlay} scrollX={scrollX} visible={showSenses} />
      </div>
      {!gameUrl && <div className="wait">Starting the run…</div>}
    </div>
  )
}
