import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Fly } from '../api/models'
import { KnobSlider } from '../components/Knobs'
import { Overlay } from '../components/RunStage'
import { byObjectOrder, splitLabel } from '../components/senseUtil'
import { errText, useStartRun } from '../hooks'
import { momentPictures } from '../draft'

const toggleIn = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

export default function MomentScreen() {
  const { momentId = '' } = useParams()
  const nav = useNavigate()
  const [edited, setFly] = useState<Fly | null>(null)
  const [showSenses, setShowSenses] = useState(true)
  const [naming, setNaming] = useState(false)
  const [typedName, setNewName] = useState<string | null>(null)
  const moment = useQuery({ queryKey: ['moment', momentId], queryFn: () => api.getMoment(momentId) })
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const siblings = useQuery({
    queryKey: ['run-moments', moment.data?.run_id], enabled: !!moment.data,
    queryFn: () => api.getRunMoments(moment.data!.run_id), staleTime: 0,
  })
  // The list of tries must be fresh every time the screen opens: a run may have just finished.
  const tries = useQuery({ queryKey: ['tries', momentId], queryFn: () => api.getTries(momentId), staleTime: 0 })
  const save = useMutation({ mutationFn: (f: Fly) => api.saveFly(f) })
  const resume = useStartRun()

  if (moment.isError) return <p role="alert">{errText(moment.error)}</p>
  if (!moment.data || !registry.data) return <p>Loading…</p>
  const m = moment.data
  const fly = edited ?? m.fly
  const newName = typedName ?? `${fly.name}-2`
  const reg = registry.data
  const level = m.scene.level_id

  const cols = reg.senses.filter((s) => s.scope === 'per_object')
  const rows = byObjectOrder(reg.objects.filter((o) => m.on_screen.includes(o.name)))
  const whole = reg.senses.filter((s) => s.scope === 'whole_fly')
  const toggle = (sense: string, obj: string) => {
    const cur = fly.attachments[sense] ?? []
    setFly({ ...fly, attachments: { ...fly.attachments, [sense]: toggleIn(cur, obj) } })
  }
  // Key knobs: the first knob of every sense that is on, compared with the fly this moment was saved with.
  const live = new Set([...Object.entries(fly.attachments).filter(([, v]) => v.length).map(([k]) => k), ...fly.whole_fly])
  const keyKnobs = reg.senses.filter((s) => live.has(s.name)).flatMap((s) => s.knobs.slice(0, 1))
  const pic = momentPictures.get(momentId)
  const resumeNow = () => resume.mutate({ fly, scene: m.scene, from_moment: momentId })

  return (
    <div className="moment">
      <section>
        <button className="back" onClick={() => nav(-1)}>‹ Back to the run</button>
        <h1 className="title">Change &amp; try again</h1>
        <p className="lead">Paused at a saved moment. Change the fly, then carry on from exactly here: same game, same brain state.</p>
        <div className="stage-box">
          <div className="stage frozen" data-testid="stage">
            {pic
              ? <div className="still"><img className="pic" data-testid="picture" alt="the game, frozen at this moment" src={`data:image/png;base64,${pic.game}`} />
                  <Overlay items={pic.overlay} scrollX={pic.scrollX} visible={showSenses} /></div>
              : <p className="muted">No picture was kept for this moment (it was saved in an earlier session).</p>}
          </div>
        </div>
        <div className="momentbar">
          <b style={{ fontWeight: 400 }}>Moment:</b>
          {(siblings.data ?? [m]).map((s) => (
            <button key={s.id} className={`chip ${s.id === momentId ? 'on' : ''}`} onClick={() => nav(`/moment/${encodeURIComponent(s.id)}`)}>◆ {s.name}</button>
          ))}
          <span className="grow" />
          <label className="check"><input type="checkbox" checked={showSenses} onChange={(e) => setShowSenses(e.target.checked)} />Show senses</label>
        </div>
        <section className="box tries">
          <h2 className="label">Tries from this moment</h2>
          {tries.data?.length ? tries.data.map((t, i) => (
            <div className="try" key={t.run_id} data-testid="try">
              <span className="n">Try {i + 1}</span>
              <span>{t.change || 'The fly as it was'}</span>
              <span className={t.outcome === 'flag' ? 'ok' : 'bad'}>{t.outcome === 'flag' ? `reached the flag` : `${t.outcome} x ${Math.round(t.max_x)}`}</span>
            </div>
          )) : <p className="muted">No tries yet.</p>}
        </section>
      </section>

      <aside className="side">
        <section className="box">
          <h2 className="label">Senses on things here</h2>
          <p className="lead" style={{ marginTop: 0, fontSize: 15 }}>Only the things on screen. Full grid on the Fly page.</p>
          {rows.length ? (
            <div className="mini-grid" style={{ gridTemplateColumns: `1fr repeat(${cols.length}, 3.6rem)` }}>
              <span />
              {cols.map((s) => <span className="h" key={s.name} style={{ color: s.colour }}>{splitLabel(s.label)[0].split(' ')[0].replace(/ing$/, '')}</span>)}
              {rows.map((o) => (
                <div key={o.name} style={{ display: 'contents' }}>
                  <span>{o.label}</span>
                  {cols.map((s) => (
                    <span className="c check" key={s.name}>
                      <input type="checkbox" aria-label={`${splitLabel(s.label)[0]} on ${o.label}`}
                        checked={(fly.attachments[s.name] ?? []).includes(o.name)} onChange={() => toggle(s.name, o.name)} />
                    </span>
                  ))}
                </div>
              ))}
            </div>
          ) : <p className="muted">Nothing the senses know about is on screen here.</p>}
          {whole.map((s) => (
            <div key={s.name}>
              <div className="sep" />
              <div className="row spread">
                <span>{splitLabel(s.label)[0]} (whole fly)</span>
                <span className="check"><input type="checkbox" aria-label={splitLabel(s.label)[0]} checked={fly.whole_fly.includes(s.name)}
                  onChange={() => setFly({ ...fly, whole_fly: toggleIn(fly.whole_fly, s.name) })} /></span>
              </div>
            </div>
          ))}
        </section>

        <section className="box">
          <h2 className="label">Tune</h2>
          {keyKnobs.length
            ? keyKnobs.map((k) => <KnobSlider key={k.key} knob={k} fly={fly} onChange={setFly} compact baseline={m.fly.knobs[k.key] ?? k.position} />)
            : <p className="muted">Switch a sense on to tune it.</p>}
        </section>
        <p className="note">New senses start quiet from this moment; senses already on keep their brain state.</p>
        {naming && (
          <div className="namebar">
            <input type="text" aria-label="new fly name" value={newName} onChange={(e) => setNewName(e.target.value)} />
            <button className="btn sm" onClick={() => save.mutate({ ...fly, name: newName })}>Save</button>
          </div>
        )}
        <div className="foot">
          <button className="btn" onClick={() => setNaming(!naming)}>Save as new fly</button>
          <button className="btn gold big" onClick={resumeNow} disabled={resume.isPending}>▶ Resume from here</button>
        </div>
        {save.isSuccess && <p className="ok">saved</p>}
        {save.isError && <p className="err" role="alert">{errText(save.error)}</p>}
        {resume.isError && <p className="err" role="alert">{errText(resume.error)}</p>}
        <p className="muted" style={{ fontSize: 14 }}>Level {level}</p>
      </aside>
    </div>
  )
}
