import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ObjectInfo } from '../api/models'
import { iconUrl } from '../api/client'

const RETRY_MS = 4000
const RETRIES = 100

/** The largest whole factor at which a natural-size picture fits the box, in device pixels (min 1). */
function wholeFactor(natW: number, natH: number, boxW: number, boxH: number, dpr: number): number {
  const eps = 1e-6
  return Math.max(1, Math.floor(Math.min((boxW * dpr) / natW, (boxH * dpr) / natH) + eps))
}

/** An object's picture (cropped from the game by the server at its native size, which makes the set in the background
 *  after it starts). The box is fixed (`.sprite`); the picture is drawn at a whole multiple of its natural size in DEVICE
 *  pixels, centred, so Windows display scaling never resamples it by a fraction. Until the picture has loaded, and if it
 *  cannot be made: a plain square in the kind's colour with the object's first letter. A missing picture is asked for
 *  again every few seconds, so it appears as soon as it is ready; nothing waits. */
export default function ObjectIcon({ object }: { object: ObjectInfo }) {
  const [loaded, setLoaded] = useState(false)
  const [tries, setTries] = useState(0)
  const [failed, setFailed] = useState(false)
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)
  const [layoutKey, setLayoutKey] = useState(0)
  const box = useRef<HTMLSpanElement>(null)
  const img = useRef<HTMLImageElement>(null)
  useEffect(() => {
    if (!failed || tries >= RETRIES) return
    const t = setTimeout(() => { setFailed(false); setTries((n) => n + 1) }, RETRY_MS)
    return () => clearTimeout(t)
  }, [failed, tries])
  useEffect(() => {
    let mq: MediaQueryList | undefined
    const watch = () => {
      mq?.removeEventListener('change', redo)
      mq = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`)
      mq.addEventListener('change', redo)
    }
    const redo = () => { setLayoutKey((n) => n + 1); watch() }
    window.addEventListener('resize', redo)
    watch()
    return () => { window.removeEventListener('resize', redo); mq?.removeEventListener('change', redo) }
  }, [])
  useLayoutEffect(() => {
    const b = box.current, i = img.current
    if (!b || !i || !loaded || !i.naturalWidth || !i.naturalHeight) return
    const dpr = window.devicePixelRatio || 1
    const r = b.getBoundingClientRect()
    const k = wholeFactor(i.naturalWidth, i.naturalHeight, r.width, r.height, dpr)
    setSize({ w: (i.naturalWidth * k) / dpr, h: (i.naturalHeight * k) / dpr })
  }, [loaded, layoutKey, tries])
  const plain = (
    <span className={`sprite plain ${object.kind}`} data-testid="object-icon" data-state="plain" aria-hidden>{object.label.charAt(0)}</span>
  )
  if (!object.icon) return plain
  return (
    <>
      {!loaded && plain}
      {!failed && (
        <span ref={box} className="sprite frame" style={loaded ? undefined : { display: 'none' }}>
          <img ref={img} className="sprite-img" data-testid={loaded ? 'object-icon' : undefined} data-state="image" alt=""
            style={size ? { width: size.w, height: size.h } : undefined} src={`${iconUrl(object.icon)}${tries ? `?r=${tries}` : ''}`}
            onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />
        </span>
      )}
    </>
  )
}
