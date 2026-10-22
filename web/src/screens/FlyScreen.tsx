import { useEffect, useState, type CSSProperties } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Fly } from '../api/models'
import SenseGrid from '../components/SenseGrid'
import { OBJECT_TABS, byOrder, splitLabel, tabOf } from '../components/senseUtil'
import { AdvancedDrawer, type KnobSection } from '../components/Knobs'
import { errText, useStartRun } from '../hooks'
import { useDraft } from '../draft'

const toggleIn = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

/** The mini brain map follows the fly's senses and actions (not its sliders), after a short pause so toggling is not laggy. */
function useBrainMap(fly: Fly) {
  const [url, setUrl] = useState('')
  const key = JSON.stringify([fly.attachments, fly.whole_fly, fly.actions, fly.loom_shapes])
  useEffect(() => {
    let live = true
    const t = setTimeout(() => {
      api.getBrainMap(fly).then((u) => { if (live) setUrl((old) => { if (old) URL.revokeObjectURL(old); return u }) }).catch(() => {})
    }, 250)
    return () => { live = false; clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return url
}

export default function FlyScreen() {
  const { scene, fly, setFly, dials, setDials } = useDraft()
  const [open, setOpen] = useState(false)
  const [naming, setNaming] = useState(false)
  const [tab, setTab] = useState(OBJECT_TABS[0].id)
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const save = useMutation({ mutationFn: (f: Fly) => api.saveFly(f, true) })
  const run = useStartRun()
  const brainMap = useBrainMap(fly)
  if (!registry.data) return <p>Loading…</p>
  const reg = registry.data
  const rows = reg.objects.filter((o) => tabOf(o) === tab)      // every registered object type, grouped by kind
  const wholeSenses = reg.senses.filter((s) => s.scope === 'whole_fly')

  const attached = new Set(Object.entries(fly.attachments).filter(([, v]) => v.length).map(([k]) => k))
  const senseOn = (n: string) => attached.has(n) || fly.whole_fly.includes(n)
  const sections: KnobSection[] = [
    ...reg.senses.filter((s) => senseOn(s.name) && s.knobs.length).map((s) => ({ key: s.name, title: splitLabel(s.label)[0], colour: s.colour, knobs: s.knobs })),
    ...reg.actions.filter((a) => fly.actions.includes(a.name) && a.knobs.length).map((a) => ({ key: a.name, title: a.label, colour: '#ffffff', knobs: a.knobs })),
  ]
  const seen = new Set<string>()
  for (const s of sections) s.knobs = s.knobs.filter((k) => !seen.has(k.key) && !!seen.add(k.key))   // a knob shared by two senses shows once
  const nSenses = reg.senses.filter((s) => senseOn(s.name)).length
  const nTuned = Object.values(fly.dials ?? {}).filter((d) => d.tuned).length
  const tunedNote = nTuned ? `${nTuned} knob${nTuned === 1 ? '' : 's'} changed by evolution.` : 'No knob changed by evolution.'
  const startRun = () => run.mutate({ fly, scene, from_moment: null, dials })

  return (
    <>
      <div className={`fly ${open ? 'dim-page' : ''}`}>
        <section>
          <div className="fly-head">
            <div>
              <h1 className="title">What does the fly sense?</h1>
              <p className="lead">Each row is a thing in the level. Any sense can be given to any thing. Open a sense&apos;s lab to see how it works.</p>
            </div>
            <label className="preset">Preset
              <select aria-label="preset" value={reg.presets.includes(fly.name) ? fly.name : ''}
                onChange={async (e) => setFly(await api.getFly(e.target.value))}>
                <option value="" disabled>choose…</option>
                {reg.presets.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
          </div>
          <div className="chips object-tabs" role="tablist" aria-label="Kind of thing">
            {OBJECT_TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} className={`chip ${tab === t.id ? 'on' : ''}`}
                onClick={() => setTab(t.id)}>{t.label}</button>
            ))}
          </div>
          <SenseGrid objects={rows} senses={reg.senses} shapes={reg.shapes} fly={fly} onChange={setFly} />

          <div className="cols2">
            <section className="box">
              <h2 className="label">Whole-fly senses</h2>
              <div className="whole">
                {wholeSenses.map((s) => {
                  const [name, what] = splitLabel(s.label)
                  return (
                    <label className="whole-row" key={s.name} style={{ '--c': s.colour } as CSSProperties} title={s.effect}>
                      <span className="dot" />
                      <span className="what"><b>{name}</b><small>{what}</small></span>
                      <span className="check">
                        <input type="checkbox" aria-label={name} checked={fly.whole_fly.includes(s.name)}
                          onChange={() => setFly({ ...fly, whole_fly: toggleIn(fly.whole_fly, s.name) })} />
                      </span>
                    </label>
                  )
                })}
              </div>
            </section>
            <section className="box">
              <h2 className="label">What the fly can do</h2>
              <div className="actions">
                {byOrder(reg.actions).map((a) => (
                  <button key={a.name} className={`action ${a.status === 'soon' ? 'off' : ''}`} disabled={a.status === 'soon'}
                    aria-pressed={fly.actions.includes(a.name)} style={fly.actions.includes(a.name) || a.status === 'soon' ? undefined : { background: '#000', borderColor: '#666', boxShadow: 'none' }}
                    onClick={() => setFly({ ...fly, actions: toggleIn(fly.actions, a.name) })}>
                    {a.label}{a.status === 'soon' ? ' (soon)' : ''}<small>{a.button}</small>
                  </button>
                ))}
              </div>
            </section>
          </div>
        </section>

        <aside>
          <section className="box this-fly">
            <h2 className="label">This fly</h2>
            <p>{fly.name} · {nSenses} senses on · {fly.actions.length} actions</p>
            <div className="brainmap">{brainMap && <img src={brainMap} alt="the neuron groups this fly uses, at their real somas" />}</div>
            <div className="legend">
              <span><i style={{ background: 'var(--teal)' }} />Teal = from the real fly brain</span>
              <span><i style={{ background: 'var(--orange)' }} />Orange = invented by us</span>
            </div>
          </section>
          <div className="dials" role="group" aria-label="Dials">
            <span className="label">Dials</span>
            {(['original', 'tuned'] as const).map((d) => (
              <button key={d} className={`chip ${dials === d ? 'on' : ''}`} aria-pressed={dials === d} onClick={() => setDials(d)}>
                {d === 'original' ? 'Original' : 'Tuned'}
              </button>
            ))}
            <small>{dials === 'original' ? 'Every knob at the value set by hand before evolution.' : tunedNote}</small>
          </div>
          <button className="adv-toggle" onClick={() => { window.scrollTo(0, 0); setOpen(true) }} aria-expanded={open}>
            <span>Advanced: fine-tune</span><span>›</span>
          </button>
          <div className="fly-foot">
            <button className="btn" onClick={() => setNaming(!naming)}>Save fly as…</button>
            <button className="btn gold big" onClick={startRun} disabled={run.isPending}>▶ Run</button>
          </div>
          {naming && (
            <div className="namebar">
              <input type="text" aria-label="fly name" value={fly.name} onChange={(e) => setFly({ ...fly, name: e.target.value })} />
              <button className="btn sm" onClick={() => save.mutate(fly)}>Save</button>
            </div>
          )}
          {save.isSuccess && <p className="ok" style={{ marginTop: 8 }}>saved as {fly.name}</p>}
          {save.isError && <p className="err" role="alert">{errText(save.error)}</p>}
          {run.isError && <p className="err" role="alert">{errText(run.error)}</p>}
        </aside>
      </div>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      {open && <AdvancedDrawer sections={sections} fly={fly} original={dials === 'original'} onChange={setFly} onClose={() => setOpen(false)} onRun={startRun} running={run.isPending} />}
    </>
  )
}
