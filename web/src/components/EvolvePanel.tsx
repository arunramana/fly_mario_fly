import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Fly } from '../api/models'
import { errText } from '../hooks'
import { useDraft } from '../draft'
import TestPanel from './TestPanel'

const GENERATIONS = [2, 5, 10, 15, 30]

/** "Evolve this fly" and "Test this fly (10 starts)": both run in the background; the test's result opens below. */
export default function EvolvePanel({ fly }: { fly: Fly }) {
  const nav = useNavigate()
  const { scene, dials, lastRunId } = useDraft()
  const [level, setLevel] = useState(scene.level_id)
  const [gens, setGens] = useState(15)
  const [start, setStart] = useState('level_start')
  const [quick, setQuick] = useState(false)
  const [testId, setTestId] = useState<string | null>(null)
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const moments = useQuery({ queryKey: ['moments', lastRunId], queryFn: () => api.getRunMoments(lastRunId!), enabled: !!lastRunId, staleTime: 5_000 })
  const here = (moments.data ?? []).filter((m) => m.scene.level_id === level)

  const evolve = useMutation({
    mutationFn: () => api.startEvolve({ fly, dials, level, generations: gens, start, ...(quick ? { population: 4, train_n: 2 } : {}) }),
    onSuccess: (id) => nav(`/evolution/${id}`),
  })
  const test = useMutation({
    mutationFn: () => api.startTest({ fly, dials: 'both', level }),
    onSuccess: (id) => setTestId(id),
  })

  return (
    <>
      <section className="box evolve-panel" data-testid="evolve-panel">
        <h2 className="label">Improve this fly</h2>
        <div className="evolve-form">
          <label>Level
            <select aria-label="evolve level" value={level} onChange={(e) => { setLevel(e.target.value); setStart('level_start') }}>
              {(levels.data ?? [{ id: level, label: level }]).map((l) => <option key={l.id} value={l.id}>{l.id === l.label ? l.id : `${l.id} ${l.label}`}</option>)}
            </select>
          </label>
          <label>Generations
            <select aria-label="generations" value={gens} onChange={(e) => setGens(Number(e.target.value))}>
              {GENERATIONS.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </label>
          <label>Start from
            <select aria-label="start from" value={start} onChange={(e) => setStart(e.target.value)}>
              <option value="level_start">the level start</option>
              {here.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </label>
          <label className="check" style={{ alignSelf: 'flex-end' }}>
            <input type="checkbox" aria-label="quick try" checked={quick} onChange={(e) => setQuick(e.target.checked)} />
            Quick try (a small search, to see it work)
          </label>
        </div>
        <div className="row" style={{ marginTop: 14 }}>
          <button className="btn gold" onClick={() => evolve.mutate()} disabled={evolve.isPending}>Evolve this fly</button>
          <button className="btn" onClick={() => test.mutate()} disabled={test.isPending}>Test this fly (10 starts)</button>
        </div>
        <p className="note">Both run in the background; the fly&apos;s own knobs are the starting point
          {dials === 'original' ? ' (evolution starts from the original dials)' : ''}. The test plays 10 starts the fly was never tuned on.</p>
        {evolve.isError && <p className="err" role="alert">{errText(evolve.error)}</p>}
        {test.isError && <p className="err" role="alert">{errText(test.error)}</p>}
      </section>
      {testId && <TestPanel key={testId} jobId={testId} onClose={() => setTestId(null)} />}
    </>
  )
}
