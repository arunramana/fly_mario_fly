import { useEffect, useState } from 'react'
import type { ObjectInfo } from '../api/models'
import { iconUrl } from '../api/client'

const RETRY_MS = 4000
const RETRIES = 100

/** An object's picture (cropped from the game by the server, which makes the set in the background after it starts).
 *  Until the picture has loaded, and if it cannot be made: a plain square in the kind's colour with the object's first
 *  letter. A missing picture is asked for again every few seconds, so it appears as soon as it is ready; nothing waits. */
export default function ObjectIcon({ object }: { object: ObjectInfo }) {
  const [loaded, setLoaded] = useState(false)
  const [tries, setTries] = useState(0)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (!failed || tries >= RETRIES) return
    const t = setTimeout(() => { setFailed(false); setTries((n) => n + 1) }, RETRY_MS)
    return () => clearTimeout(t)
  }, [failed, tries])
  const plain = (
    <span className={`sprite plain ${object.kind}`} data-testid="object-icon" data-state="plain" aria-hidden>{object.label.charAt(0)}</span>
  )
  if (!object.icon) return plain
  return (
    <>
      {!loaded && plain}
      {!failed && (
        <img className="sprite" data-testid={loaded ? 'object-icon' : undefined} data-state="image" alt=""
          style={loaded ? undefined : { display: 'none' }} src={`${iconUrl(object.icon)}${tries ? `?r=${tries}` : ''}`}
          onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />
      )}
    </>
  )
}
