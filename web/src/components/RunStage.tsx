import { pngSize } from '../draft'

const GAME_W = 1024, GAME_H = 960 // the game at x4: the canvas the overlay's [x, y] is on

/** The overlay picture placed on the game box. It is cropped to what was drawn, so its size and offset become percentages. */
export function Overlay({ png, at, visible }: { png?: string | null; at?: number[] | null; visible: boolean }) {
  if (!png || !at) return null
  const [w, h] = pngSize(png)
  return (
    <img className="ov" data-testid="overlay" alt="" src={`data:image/png;base64,${png}`}
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
  return (
    <div className={`stage ${showBrain ? '' : 'nobrain'} ${frozen ? 'frozen' : ''}`} data-testid="stage">
      {brain && <img className="brain" data-testid="brain-panel" alt="the fly's brain, neurons lit by activity" src={`data:image/jpeg;base64,${brain}`} />}
      <div className="game">
        {game && <img className="pic" data-testid="picture" alt="the game" src={`data:image/png;base64,${game}`} />}
        <Overlay png={overlay} at={at} visible={showSenses} />
      </div>
      {!game && <div className="wait">Starting the run…</div>}
    </div>
  )
}
