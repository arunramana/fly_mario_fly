import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { FlyConfig } from '../api/types'
import GameStage from '../components/GameStage'
import Knobs, { OriginKey } from '../components/Knobs'
import SenseGrid from '../components/SenseGrid'
import { useDraft } from '../state'

export default function MomentScreen() {
  const { momentId = '' } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { setLastRunId } = useDraft()
  const [edited, setFly] = useState<FlyConfig | null>(null)
  const [typedName, setNewName] = useState<string | null>(null)
  const moment = useQuery({ queryKey: ['moment', momentId], queryFn: () => api.getMoment(momentId) })
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const tries = useQuery({ queryKey: ['tries', momentId], queryFn: () => api.getTries(momentId) })
  const save = useMutation({
    mutationFn: (f: FlyConfig) => api.saveFly(f),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['registry'] }),
  })
  const resume = useMutation({
    mutationFn: (f: FlyConfig) => api.resumeFromMoment(momentId, f),
    onSuccess: ({ run_id }) => { setLastRunId(run_id); nav(`/run/${run_id}`) },
  })

  if (!moment.data || !registry.data) return <p>Loading…</p>
  const fly = edited ?? moment.data.fly
  const newName = typedName ?? `${fly.name}-2`

  const reg = registry.data
  const rows = reg.objects.filter((o) => moment.data.on_screen.includes(o.name))
  // Key knobs: the first knob of every sense currently attached or on.
  const live = new Set([...Object.entries(fly.attachments).filter(([, v]) => v.length).map(([k]) => k), ...fly.whole_fly])
  const keyKnobs = reg.senses.filter((s) => live.has(s.name)).flatMap((s) => s.knobs.slice(0, 1))

  return (
    <>
      <h2>Change &amp; try again · {moment.data.name}</h2>
      <div className="two">
        <section>
          <GameStage objects={moment.data.objects} showOverlay={false} frozen />
          <p className="muted">Frozen at frame {moment.data.frame}.</p>
        </section>
        <div>
          <section className="box">
            <h3>Senses on what is on screen</h3>
            <SenseGrid objects={rows} senses={reg.senses} fly={fly} onChange={setFly} />
          </section>
          <section className="box">
            <div className="row spread"><h3>Key knobs</h3><OriginKey /></div>
            <Knobs knobs={keyKnobs} fly={fly} onChange={setFly} />
          </section>
          <div className="row">
            <button className="gold" onClick={() => resume.mutate(fly)}>Resume from here ▶</button>
            <input type="text" aria-label="new fly name" value={newName} onChange={(e) => setNewName(e.target.value)} />
            <button onClick={() => save.mutate({ ...fly, name: newName })}>Save as new fly</button>
            {save.isSuccess && <span style={{ color: 'var(--green)' }}>saved</span>}
          </div>
        </div>
      </div>

      <section className="box" style={{ marginTop: 18 }}>
        <h3>Tries from this moment</h3>
        {tries.data?.length ? tries.data.map((t) => (
          <div className="try" key={t.id}>
            <span>{t.fly}</span>
            <span className={t.outcome === 'flag' ? 'ok' : 'bad'}>{t.outcome}</span>
            <span className="muted">{Math.round(t.max_x)} px</span>
          </div>
        )) : <p className="muted">No tries yet.</p>}
      </section>
    </>
  )
}
