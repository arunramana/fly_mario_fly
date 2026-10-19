import { useState, type CSSProperties } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { FlyConfig } from '../api/types'
import SenseGrid from '../components/SenseGrid'
import Knobs, { OriginKey } from '../components/Knobs'
import { useDraft } from '../state'

const toggleIn = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

export default function FlyScreen() {
  const { scene, fly, setFly, setLastRunId } = useDraft()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const save = useMutation({ mutationFn: (f: FlyConfig) => api.saveFly(f) })
  const run = useMutation({
    mutationFn: () => api.startRun({ fly, scene, from_moment: null }),
    onSuccess: ({ run_id }) => { setLastRunId(run_id); nav(`/run/${run_id}`) },
  })
  if (!registry.data || !levels.data) return <p>Loading…</p>
  const reg = registry.data
  const level = levels.data.find((l) => l.id === scene.level_id)
  const rows = reg.objects.filter((o) => level?.objects.includes(o.name))
  const wholeSenses = reg.senses.filter((s) => s.scope === 'whole_fly')

  // Knobs of everything switched on.
  const attached = new Set(Object.entries(fly.attachments).filter(([, v]) => v.length).map(([k]) => k))
  const knobs = [
    ...reg.senses.filter((s) => attached.has(s.name) || fly.whole_fly.includes(s.name)).flatMap((s) => s.knobs),
    ...reg.actions.filter((a) => fly.actions.includes(a.name)).flatMap((a) => a.knobs),
  ]

  return (
    <>
      <div className="row spread" style={{ marginBottom: 18 }}>
        <div className="row">
          <h2 style={{ margin: 0 }}>Fly</h2>
          <select aria-label="preset" value={reg.presets.includes(fly.name) ? fly.name : ''}
            onChange={async (e) => setFly(await api.getFly(e.target.value))}>
            <option value="" disabled>preset…</option>
            {reg.presets.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <span className="muted">Level {scene.level_id}</span>
      </div>

      <section className="box">
        <h2>Senses on objects</h2>
        <SenseGrid objects={rows} senses={reg.senses} fly={fly} onChange={setFly} />
      </section>

      <div className="two">
        <section className="box">
          <h2>Whole-fly senses</h2>
          <div className="row">
            {wholeSenses.map((s) => (
              <button key={s.name} className={`chip ${fly.whole_fly.includes(s.name) ? 'on' : ''}`}
                style={{ '--c': s.colour } as CSSProperties} title={s.effect}
                onClick={() => setFly({ ...fly, whole_fly: toggleIn(fly.whole_fly, s.name) })}>
                <span className={`swatch ${s.line}`} />{s.label}
              </button>
            ))}
          </div>
        </section>
        <section className="box">
          <h2>Actions</h2>
          <div className="row">
            {reg.actions.map((a) => (
              <button key={a.name} className={`chip ${fly.actions.includes(a.name) ? 'on' : ''}`}
                disabled={a.status === 'soon'}
                onClick={() => setFly({ ...fly, actions: toggleIn(fly.actions, a.name) })}>
                {a.label}{a.status === 'soon' && <span className="soon">soon</span>}
              </button>
            ))}
          </div>
        </section>
      </div>

      <section className="box">
        <div className="row spread">
          <button onClick={() => setOpen(!open)} aria-expanded={open}>{open ? '▼' : '▶'} Advanced</button>
          <OriginKey />
        </div>
        {open && (knobs.length ? <Knobs knobs={knobs} fly={fly} onChange={setFly} /> : <p className="muted">Switch something on to tune it.</p>)}
      </section>

      <div className="row spread">
        <div className="row">
          <input type="text" aria-label="fly name" value={fly.name} onChange={(e) => setFly({ ...fly, name: e.target.value })} />
          <button onClick={() => save.mutate(fly)}>Save fly</button>
          {save.isSuccess && <span style={{ color: 'var(--green)' }}>saved</span>}
        </div>
        <button className="gold" onClick={() => run.mutate()} disabled={run.isPending}>Run ▶</button>
      </div>
    </>
  )
}
