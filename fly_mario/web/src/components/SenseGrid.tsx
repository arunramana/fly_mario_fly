import type { CSSProperties } from 'react'
import type { FlyConfig, ObjectInfo, SenseInfo } from '../api/types'

interface Props {
  objects: ObjectInfo[] // rows
  senses: SenseInfo[] // all registry senses; per_object ones become columns
  fly: FlyConfig
  onChange: (fly: FlyConfig) => void
}

/** Rows = objects, columns = per-object senses; one toggle per cell, coloured by sense. */
export default function SenseGrid({ objects, senses, fly, onChange }: Props) {
  const cols = senses.filter((s) => s.scope === 'per_object')

  const toggle = (sense: string, obj: string) => {
    const cur = fly.attachments[sense] ?? []
    const next = cur.includes(obj) ? cur.filter((o) => o !== obj) : [...cur, obj]
    onChange({ ...fly, attachments: { ...fly.attachments, [sense]: next } })
  }

  return (
    <table className="grid-table">
      <thead>
        <tr>
          <th />
          {cols.map((s) => (
            <th key={s.name} style={{ '--c': s.colour } as CSSProperties} title={s.effect}>
              <span className={`swatch ${s.line}`} />{s.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {objects.map((o) => (
          <tr key={o.name}>
            <th className="rowh" title={o.note}>{o.label}</th>
            {cols.map((s) => {
              const on = (fly.attachments[s.name] ?? []).includes(o.name)
              return (
                <td key={s.name}>
                  <button
                    className={`cell ${s.line} ${on ? 'on' : ''}`}
                    style={{ '--c': s.colour } as CSSProperties}
                    aria-pressed={on}
                    aria-label={`${s.label} on ${o.label}`}
                    onClick={() => toggle(s.name, o.name)}
                  />
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
