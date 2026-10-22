import { useEffect, useMemo } from 'react'
import { pngSize } from '../draft'

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

const GAME_W = 1024, GAME_H = 960 // the game at x4: the canvas the overlay's [x, y] is on

/** The overlay picture placed on the game box. It is cropped to what was drawn, so its size and offset become percentages. */
export function Overlay({ png, at, visible }: { png?: string | null; at?: number[] | null; visible: boolean }) {
  const src = useBlobUrl(png, 'image/png')
  if (!png || !at || !src) return null
  const [w, h] = pngSize(png)
  return (
    <img className="ov" data-testid="overlay" alt="" src={src}
      style={{ left: `${(at[0] / GAME_W) * 100}%`, top: `${(at[1] / GAME_H) * 100}%`, width: `${(w / GAME_W) * 100}%`, height: `${(h / GAME_H) * 100}%`, visibility: visible ? 'visible' : 'hidden' }} />
  )
}

/**
 * The picture of a run, 1920 x 1080 like the videos: the R3 brain panel on the left, the NES screen at x4 on the right with
 * the senses overlay on top. Three separate layers, so "Show senses" and "Show brain" are only a visibility flip: nothing
 * is re-rendered. Without the brain the game slides to the middle, as in the videos made with --no-brain.
 */
export default function RunStage({ brain, game, overlay, at, showBrain, showSenses, frozen }: {
  brain?: string
  game?: string
  overlay?: string | null
  at?: number[] | null
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
        <Overlay png={overlay} at={at} visible={showSenses} />
      </div>
      {!gameUrl && <div className="wait">Starting the run…</div>}
    </div>
  )
}
