import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Scene } from '../api/types'
import { useDraft } from '../state'

type Mods = Scene['modifiers']
const sameMods = (a: Mods, b: Mods) => JSON.stringify(a) === JSON.stringify(b)

export default function SceneScreen() {
  const { scene, setScene } = useDraft()
  const nav = useNavigate()
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const moments = useQuery({ queryKey: ['moments'], queryFn: api.getMoments })
  if (!levels.data || !registry.data) return <p>Loading…</p>

  const level = levels.data.find((l) => l.id === scene.level_id)
  const startKind = scene.start === 'level_start' ? 'level_start' : typeof scene.start === 'number' ? 'point' : 'moment'

  // Test-scene chips come from registry data: "Whole level", each plain modifier, each per-object modifier x object.
  const chips: { key: string; label: string; mods: Mods }[] = [{ key: 'whole', label: 'Whole level', mods: [] }]
  for (const m of registry.data.scene_modifiers) {
    if (!m.per_object) chips.push({ key: m.name, label: m.label, mods: [[m.name, {}]] })
    else for (const o of registry.data.objects)
      chips.push({ key: `${m.name}:${o.name}`, label: m.label.replace('{object}', o.label), mods: [[m.name, { object: o.name }]] })
  }

  const setStart = (start: Scene['start']) => setScene({ ...scene, start })

  return (
    <>
      <section className="box">
        <h2>1 · Pick a level</h2>
        <div className="level-grid">
          {levels.data.map((l) => (
            <button
              key={l.id}
              className={`level ${scene.level_id === l.id ? 'on' : ''} ${l.status === 'locked' ? 'locked' : ''}`}
              disabled={l.status === 'locked'}
              onClick={() => setScene({ ...scene, level_id: l.id })}
            >
              <b>{l.label}</b>
              {l.kind} · <span className={`status-${l.status}`}>{l.status}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="box">
        <h2>2 · Test scene</h2>
        <div className="row">
          {chips.map((c) => (
            <button key={c.key} className={`chip ${sameMods(scene.modifiers, c.mods) ? 'on' : ''}`}
              onClick={() => setScene({ ...scene, modifiers: c.mods })}>
              {c.label}
            </button>
          ))}
        </div>
      </section>

      <section className="box">
        <h2>3 · Start from</h2>
        <div className="row">
          <button className={`chip ${startKind === 'level_start' ? 'on' : ''}`} onClick={() => setStart('level_start')}>Level start</button>
          <button className={`chip ${startKind === 'point' ? 'on' : ''}`} onClick={() => setStart(typeof scene.start === 'number' ? scene.start : 0)}>Point on strip</button>
          <button className={`chip ${startKind === 'moment' ? 'on' : ''}`}
            disabled={!moments.data?.length}
            onClick={() => moments.data?.[0] && setStart(moments.data[0].id)}>Saved moment</button>
        </div>
        {startKind === 'point' && level && (
          <div className="strip" role="slider" aria-label="start point"
            onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect()
              setStart(Math.round(((e.clientX - r.left) / r.width) * level.width))
            }}>
            <div className="pin" style={{ left: `${(Number(scene.start) / level.width) * 100}%` }} />
          </div>
        )}
        {startKind === 'moment' && (
          <select value={String(scene.start)} onChange={(e) => setStart(e.target.value)} style={{ marginTop: 10 }}>
            {moments.data?.map((m) => <option key={m.id} value={m.id}>{m.name} · frame {m.frame}</option>)}
          </select>
        )}
      </section>

      <div className="row spread">
        <span className="muted">Level {scene.level_id}{level ? ` · ${level.kind}` : ''}</span>
        <button className="gold" onClick={() => nav('/fly')}>Next ▶</button>
      </div>
    </>
  )
}
