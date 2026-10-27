import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, thumbnailUrl } from '../api/client'
import type { LevelInfo, Scene } from '../api/models'
import { everythingPicked, loadScenes, saveScene, useDraft } from '../draft'
import { FEATURES } from '../features'

type Mods = Scene['modifiers']
const sameMods = (a: Mods, b: Mods) => JSON.stringify(a) === JSON.stringify(b)
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
const KIND_ORDER = ['overground', 'underground', 'athletic', 'water', 'castle', 'mixed']

function statusClass(l: LevelInfo) {
  return l.status === 'cleared' ? 'ok' : l.status_text.startsWith('best') ? 'bad' : ''
}
/** "best x 891" means it was tried and never won: the wireframe says where it died. */
const statusText = (l: LevelInfo) => l.status_text.replace(/^best x/, 'dies at x')

export default function SceneScreen() {
  const { scene, setScene, picked, setPicked } = useDraft()
  const nav = useNavigate()
  const [kind, setKind] = useState('all')
  const [saved, setSaved] = useState(false)
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const runs = useQuery({ queryKey: ['runs'], queryFn: api.getRuns, enabled: FEATURES.moments })
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

  const all = levels.data
  const level = all.find((l) => l.id === scene.level_id)
  const kinds = KIND_ORDER.filter((k) => all.some((l) => l.kind === k))
  const shown = kind === 'all' ? all : all.filter((l) => l.kind === kind)
  const startKind = scene.start === 'level_start' ? 'level_start' : 'moment'
  const objLabel = (n: string) => registry.data.objects.find((o) => o.name === n)?.label ?? n
  const objOrder = (n: string) => registry.data.objects.find((o) => o.name === n)?.order ?? 1000      // the API's display order

  // Test-scene chips come from registry data: each modifier that takes no parameters (Whole level, No enemies).
  const chips: { key: string; label: string; mods: Mods }[] = registry.data.scene_modifiers
    .filter((m) => !m.params.length).map((m) => ({ key: m.name, label: m.label, mods: [[m.name, {}]] }))

  const setStart = (start: Scene['start']) => { setScene({ ...scene, start }); setPicked({ ...picked, start: true }) }
  const pickLevel = (l: LevelInfo) => { setScene({ ...scene, level_id: l.id, start: 'level_start' }); setPicked({ ...picked, level: true, start: FEATURES.lite }) }
  const missing = [!picked.level && 'a level', !picked.test && 'a test scene', !picked.start && 'a start'].filter(Boolean) as string[]
  const ready = missing.length === 0
  const sceneName = `${level?.label ?? scene.level_id} · ${chips.find((c) => sameMods(c.mods, scene.modifiers))?.label ?? 'custom'}`

  return (
    <div className="scene">
      <section>
        <div className="scene-head">
          <h1 className="title">Where does the fly play?</h1>
          <div className="filters">
            {['all', ...kinds].map((k) => (
              <button key={k} className={`chip ${kind === k ? 'on' : ''}`} onClick={() => setKind(k)}>{cap(k)}</button>
            ))}
          </div>
        </div>
        <div className="level-grid" data-testid="level-grid">
          {shown.map((l) => (
            <button key={l.id} className={`level ${picked.level && scene.level_id === l.id ? 'on' : ''}`} data-level={l.id}
              aria-pressed={picked.level && scene.level_id === l.id} onClick={() => pickLevel(l)}>
              <span className="thumb"><img src={thumbnailUrl(l.id)} alt="" loading="lazy" /></span>
              <span className="level-line">
                <span className="level-id">{l.label}</span>
                <span className="level-kind">{cap(l.kind)}</span>
              </span>
              <span className={`level-status ${statusClass(l)}`} style={{ display: 'block' }}>{statusText(l)}</span>
            </button>
          ))}
        </div>
        <p className="caption">
          {FEATURES.lite ? `${all.length} levels on this server` : kind === 'all'
            ? `Showing ${all[0].label} to ${all[15]?.label ?? all[all.length - 1].label} · scroll for ${all[16]?.label ?? ''} … ${all[31]?.label ?? ''}, ${all.slice(32).map((l) => l.label.toLowerCase().replace('whole game', 'the whole game').replace(/^(lost levels|random stages)$/, (m) => cap(m))).join(', ')}`
            : `${shown.length} ${kind} levels`}
        </p>
      </section>

      <aside className="side">
        <section className="box">
          <div className="facts-top">
            <h2 className="label">{level?.label ?? scene.level_id} · {cap(level?.kind ?? '')}</h2>
            {level && <span className={statusClass(level)}>{statusText(level)}</span>}
          </div>
          <div className="strip-preview">
            <img src={thumbnailUrl(scene.level_id)} alt={`${level?.label ?? scene.level_id} opening screen`} />
          </div>
          <p className="facts">
            {level?.objects == null
              ? 'Not scanned yet: every kind of thing is offered on the Fly page.'
              : `Things found in this level: ${[...level.objects].sort((a, b) => objOrder(a) - objOrder(b)).map(objLabel).join(', ') || 'none'}${level.partial ? ' (so far)' : ''}.`}
          </p>
        </section>

        <section className="box">
          <h2 className="label">Test scene</h2>
          <p className="lead" style={{ marginTop: 0 }}>Play the whole level, or the level with every enemy removed.</p>
          <div className="row" style={{ marginTop: 14, gap: 10 }}>
            {chips.map((c) => (
              <button key={c.key} className={`chip test ${picked.test && sameMods(scene.modifiers, c.mods) ? 'on' : ''}`}
                onClick={() => { setScene({ ...scene, modifiers: c.mods }); setPicked({ ...picked, test: true }) }}>{c.label}</button>
            ))}
          </div>
          {FEATURES.moments && <div className="group">
            <h3>Start from</h3>
            <label className="radio"><input type="radio" name="start" checked={picked.start && startKind === 'level_start'} onChange={() => setStart('level_start')} />the level start</label>
            <label className="radio"><input type="radio" name="start" checked={picked.start && startKind === 'moment'} disabled={!moments.data?.length}
              onChange={() => moments.data?.[0] && setStart(moments.data[0].id)} />a saved moment</label>
            {startKind === 'moment' && (
              <select aria-label="saved moment" value={String(scene.start)} onChange={(e) => setStart(e.target.value)}>
                {moments.data?.map((m) => <option key={m.id} value={m.id}>{level?.label ?? m.scene.level_id} · {m.name} (x {Math.round(m.x)})</option>)}
              </select>
            )}
          </div>}
        </section>

        <div className="scene-foot">
        <div className="foot">
          <button className="btn" onClick={() => { saveScene({ name: sceneName, scene }); setSaved(true) }}>{saved ? 'Scene saved' : 'Save scene'}</button>
          {loadScenes().length > 0 && (
            <select aria-label="saved scene" value="" onChange={(e) => { const s = loadScenes().find((x) => x.name === e.target.value); if (s) { setScene(s.scene); setPicked(everythingPicked) } }}>
              <option value="" disabled>Load a saved scene…</option>
              {loadScenes().map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
          )}
          <button className="btn gold big" disabled={!ready} aria-describedby="scene-missing" onClick={() => nav('/fly')}>Next: choose the fly →</button>
        </div>
        <p id="scene-missing" className={`missing ${ready ? 'ok' : ''}`} data-testid="scene-missing">
          {ready ? 'Level, test scene and start are chosen.' : `Still to choose: ${missing.join(', ')}.`}
        </p>
        </div>
      </aside>
    </div>
  )
}
