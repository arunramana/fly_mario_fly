import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Fly } from '../api/models'
import GameStage from '../components/GameStage'
import Knobs, { OriginKey } from '../components/Knobs'
import SenseGrid from '../components/SenseGrid'
import { momentPictures, useDraft } from '../state'

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function MomentScreen() {
  const { momentId = '' } = useParams()
  const nav = useNavigate()
  const { setLastRunId } = useDraft()
  const [edited, setFly] = useState<Fly | null>(null)
  const [typedName, setNewName] = useState<string | null>(null)
  const moment = useQuery({ queryKey: ['moment', momentId], queryFn: () => api.getMoment(momentId) })
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  // The list of tries must be fresh every time the screen opens: a run may have just finished.
  const tries = useQuery({ queryKey: ['tries', momentId], queryFn: () => api.getTries(momentId), staleTime: 0 })
  const save = useMutation({ mutationFn: (f: Fly) => api.saveFly(f) })
  const resume = useMutation({
    mutationFn: (f: Fly) => api.startRun({ fly: f, scene: moment.data!.scene, from_moment: momentId }),
    onSuccess: ({ run_id }) => { setLastRunId(run_id); nav(`/run/${run_id}`) },
  })

  if (moment.isError) return <p role="alert">{errText(moment.error)}</p>
  if (!moment.data || !registry.data) return <p>Loading…</p>
  const m = moment.data
  const fly = edited ?? m.fly
  const newName = typedName ?? `${fly.name}-2`

  const reg = registry.data
  const rows = reg.objects.filter((o) => m.on_screen.includes(o.name))
  // Key knobs: the first knob of every sense currently attached or on.
  const live = new Set([...Object.entries(fly.attachments).filter(([, v]) => v.length).map(([k]) => k), ...fly.whole_fly])
  const keyKnobs = reg.senses.filter((s) => live.has(s.name)).flatMap((s) => s.knobs.slice(0, 1))
  const picture = momentPictures.get(momentId)

  return (
    <>
      <h2>Change &amp; try again · {m.name}</h2>
      <div className="two">
        <section>
          {picture
            ? <GameStage png={picture} showOverlay={false} frozen />
            : <div className="box muted">No picture was kept for this moment.</div>}
          <p className="muted">Frozen at frame {m.frame} · {Math.round(m.x)} px into level {m.scene.level_id}.</p>
        </section>
        <div>
          <section className="box">
            <h3>Senses on what is on screen</h3>
            {rows.length
              ? <SenseGrid objects={rows} senses={reg.senses} fly={fly} onChange={setFly} />
              : <p className="muted">Nothing the senses know about is on screen here.</p>}
          </section>
          <section className="box">
            <div className="row spread"><h3>Key knobs</h3><OriginKey /></div>
            {keyKnobs.length ? <Knobs knobs={keyKnobs} fly={fly} onChange={setFly} /> : <p className="muted">Switch a sense on to tune it.</p>}
          </section>
          <div className="row">
            <button className="gold" onClick={() => resume.mutate(fly)} disabled={resume.isPending}>Resume from here ▶</button>
            <input type="text" aria-label="new fly name" value={newName} onChange={(e) => setNewName(e.target.value)} />
            <button onClick={() => save.mutate({ ...fly, name: newName })}>Save as new fly</button>
            {save.isSuccess && <span style={{ color: 'var(--green)' }}>saved</span>}
            {save.isError && <span style={{ color: 'var(--red)' }} role="alert">{errText(save.error)}</span>}
            {resume.isError && <span style={{ color: 'var(--red)' }} role="alert">{errText(resume.error)}</span>}
          </div>
        </div>
      </div>

      <section className="box" style={{ marginTop: 18 }}>
        <h3>Tries from this moment</h3>
        {tries.data?.length ? tries.data.map((t) => (
          <div className="try" key={t.run_id} data-testid="try">
            <span>{t.change || 'same fly'}</span>
            <span className={t.outcome === 'flag' ? 'ok' : 'bad'}>{t.outcome}</span>
            <span className="muted">{Math.round(t.max_x)} px</span>
          </div>
        )) : <p className="muted">No tries yet.</p>}
      </section>
    </>
  )
}
