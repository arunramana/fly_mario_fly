import type { CSSProperties } from 'react'
import type { Fly, ObjectInfo, SenseInfo, ShapeInfo } from '../api/models'
import ObjectIcon from './ObjectIcon'
import { byOrder, splitLabel } from './senseUtil'

const shapeWords = (shape?: ShapeInfo) => {
  if (!shape) return ''
  const l = shape.label.charAt(0).toLowerCase() + shape.label.slice(1)
  return `looms as ${/^(its|the|a|an) /.test(l) ? l : `a ${l}`}`
}

interface Props {
  objects: ObjectInfo[] // rows
  senses: SenseInfo[] // all registry senses; per_object ones become columns
  shapes: ShapeInfo[]
  fly: Fly
  onChange: (fly: Fly) => void
}

/** The sense grid of the Fly page: a row per thing in the level, a column per per-object sense, one switch per cell. */
export default function SenseGrid({ objects, senses, shapes, fly, onChange }: Props) {
  const cols = byOrder(senses.filter((s) => s.scope === 'per_object'))

  const toggle = (sense: string, obj: string) => {
    const cur = fly.attachments[sense] ?? []
    const next = cur.includes(obj) ? cur.filter((o) => o !== obj) : [...cur, obj]
    onChange({ ...fly, attachments: { ...fly.attachments, [sense]: next } })
  }

  return (
    <div className="sense-grid" style={{ '--cols': cols.length } as CSSProperties} data-testid="sense-grid">
      <div className="sg-head">
        <span>Thing in the level</span>
        {cols.map((s) => {
          const [name, what] = splitLabel(s.label)
          return (
            <div className="sg-col" key={s.name} style={{ '--c': s.colour } as CSSProperties} title={s.effect}>
              <span className={`swatch ${s.line}`} />
              <b>{name}</b>
              <small>{what}</small>
            </div>
          )
        })}
      </div>
      {objects.map((o) => {
        const shape = shapes.find((s) => s.name === (fly.loom_shapes[o.name] ?? o.default_loom_shape))
        return (
          <div className="sg-row" key={o.name}>
            <div className="sg-thing" title={o.note}>
              <ObjectIcon object={o} />
              <span><b>{o.label}</b><small>{o.kind} · {shapeWords(shape) || o.note}</small></span>
            </div>
            {cols.map((s) => {
              const on = (fly.attachments[s.name] ?? []).includes(o.name)
              return (
                <button key={s.name} className={`toggle ${on ? 'on' : ''}`} style={{ '--c': s.colour } as CSSProperties}
                  aria-pressed={on} aria-label={`${splitLabel(s.label)[0]} on ${o.label}`} onClick={() => toggle(s.name, o.name)} />
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
