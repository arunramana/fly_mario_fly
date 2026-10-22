import { useState } from 'react'
import type { ObjectInfo } from '../api/models'
import { iconUrl } from '../api/client'

/** An object's picture (cropped from the game by the server). If it cannot be made or loaded: a plain square in the
 *  kind's colour with the object's first letter. */
export default function ObjectIcon({ object }: { object: ObjectInfo }) {
  const [failed, setFailed] = useState(false)
  if (!object.icon || failed) {
    return <span className={`sprite plain ${object.kind}`} data-testid="object-icon" data-state="plain" aria-hidden>{object.label.charAt(0)}</span>
  }
  return <img className="sprite" data-testid="object-icon" data-state="image" src={iconUrl(object.icon)} alt="" onError={() => setFailed(true)} />
}
