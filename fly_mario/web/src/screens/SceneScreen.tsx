import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Scene } from '../api/models'
import { useDraft } from '../state'

type Mods = Scene['modifiers']
const sameMods = (a: Mods, b: Mods) => JSON.stringify(a) === JSON.stringify(b)

export default function SceneScreen() {
  const { scene, setScene } = useDraft()
  const nav = useNavigate()
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const runs = useQuery({ queryKey: ['runs'], queryFn: api.getRuns })
  // Saved moments of this level, newest runs first (the API lists moments per run).
  const moments = useQuery({
    queryKey: ['moments', scene.level_id, runs.data?.length ?? 0],
    enabled: !!runs.data,
    queryFn: async () => {
      const mine = (runs.data ?? []).filter((r) => r.level_id === scene.level_id).slice(-12)
      const lists = await Promise.all(mine.map((r) => api.getRunMoments(r.id).catch(() => [])))
      return lists.flat().filter((m) => m.scene.level_id === scene.level_id)
    },
  })
  if (!levels.data || !registry.data) return <p>Loading…</p>

  const level = levels.data.find((l) => l.id === scene.level_id)
  const startKind = scene.start === 'level_start' ? 'level_start' : typeof scene.start === 'number' ? 'point' : 'moment'
  const width = level?.width ?? null

  // Test-scene chips come from registry data: each plain modifier, and each object-picking modifier x each object
  // in this level (every object when the level has not been scanned). Modifiers with other parameters are not chips.
  const objects = registry.data.objects.filter((o) => !level?.objects || level.objects.includes(o.name))
  const chips: { key: string; label: string; mods: Mods }[] = []
  for (const m of registry.data.scene_modifiers) {
    const pick = m.params.find((p) => p.type === 'object_types')
    if (!m.params.length) chips.push({ key: m.name, label: m.label, mods: [[m.name, {}]] })
    else if (pick && m.params.length === 1) for (const o of objects)
      chips.push({ key: `${m.name}:${o.name}`, label: `${m.label}: ${o.label}`, mods: [[m.name, { [String(pick.key)]: [o.name] }]] })
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
              data-level={l.id}
              onClick={() => setScene({ ...scene, level_id: l.id, start: 'level_start' })}
            >
              <b>{l.label}</b>
              {l.kind} · <span className={`status-${l.status}`}>{l.status_text}</span>
              <span className="muted level-facts">
                {l.width == null ? '? px' : `${l.width}${l.partial ? '+' : ''} px`} · {l.objects == null ? '? objects' : `${l.objects.length} objects`}
              </span>
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
          <button className={`chip ${startKind === 'point' ? 'on' : ''}`} disabled={width == null}
            onClick={() => setStart(typeof scene.start === 'number' ? scene.start : 0)}>Point on strip</button>
          <button className={`chip ${startKind === 'moment' ? 'on' : ''}`}
            disabled={!moments.data?.length}
            onClick={() => moments.data?.[0] && setStart(moments.data[0].id)}>Saved moment</button>
        </div>
        {startKind === 'point' && width != null && (
          <div className="strip" role="slider" aria-label="start point"
            onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect()
              setStart(Math.round(((e.clientX - r.left) / r.width) * width))
            }}>
            <div className="pin" style={{ left: `${(Number(scene.start) / width) * 100}%` }} />
          </div>
        )}
        {startKind === 'moment' && (
          <select aria-label="saved moment" value={String(scene.start)} onChange={(e) => setStart(e.target.value)} style={{ marginTop: 10 }}>
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
