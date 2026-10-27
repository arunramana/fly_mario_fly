import { NavLink, Navigate, Route, Routes, useLocation, useMatch } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import { runRequests, useDraft } from './draft'
import SceneScreen from './screens/SceneScreen'
import FlyScreen from './screens/FlyScreen'
import RunScreen from './screens/RunScreen'
import MomentScreen from './screens/MomentScreen'
import EvolutionScreen from './screens/EvolutionScreen'
import LiteRunScreen from './screens/LiteRunScreen'
import { FEATURES } from './features'

const STEPS = ['/scene', '/fly', '/run', '/evolution']

/** The sub-title of the header: it says where you are, in the words of the wireframes. */
function Subtitle() {
  const { scene, fly } = useDraft()
  const { pathname } = useLocation()
  const runId = useMatch('/run/:runId')?.params.runId
  const registry = useQuery({ queryKey: ['registry'], queryFn: api.getRegistry })
  const levels = useQuery({ queryKey: ['levels'], queryFn: api.getLevels })
  const level = levels.data?.find((l) => l.id === scene.level_id)?.label ?? scene.level_id
  const mods = scene.modifiers
    .map(([n]) => registry.data?.scene_modifiers.find((m) => m.name === n)?.label ?? n)
    .filter((l) => l.toLowerCase() !== 'whole level')
  if (pathname.startsWith('/fly')) return <>Scene: {level}{mods.length ? ` · ${mods.join(', ').toLowerCase()}` : ''}</>
  if (pathname.startsWith('/run') && runId) {
    const info = runRequests.get(runId)
    const lv = info?.req.scene.level_id ?? scene.level_id
    return <>{levels.data?.find((l) => l.id === lv)?.label ?? lv} · {info?.req.fly.name ?? fly.name}{info ? ` · try ${info.tryNo}` : ''}</>
  }
  if (pathname.startsWith('/moment')) return <>{level} · paused at a saved moment</>
  if (pathname.startsWith('/evolution')) return <>Evolve a fly in the background, and test it</>
  return <>MaleCNS fly brain × Super Mario Bros</>
}

export default function App() {
  const { lastRunId, picked } = useDraft()
  const { pathname } = useLocation()
  const here = STEPS.findIndex((s) => pathname.startsWith(s)) + (pathname.startsWith('/moment') ? 3 : 0)
  const tab = (to: string, i: number, label: string, off = false) => (
    <NavLink to={to} className={({ isActive }) => `tab ${isActive || (i === 2 && pathname.startsWith('/moment')) ? 'active' : ''} ${off ? 'off' : ''}`}>
      {label}{i < here && i < 3 && !off ? ' ✓' : ''}
    </NavLink>
  )
  return (
    <>
      <header className="app-header">
        <span className="logo" aria-hidden />
        <NavLink to="/scene" className="brand">fly_mario_fly</NavLink>
        <span className="subtitle"><Subtitle /></span>
        <nav>
          {tab('/scene', 0, '1 Scene')}
          {tab('/fly', 1, '2 Fly', here < 1 && !(picked.level && picked.test && picked.start))}
          {tab(lastRunId ? `/run/${lastRunId}` : '/run', 2, '3 Run', !lastRunId)}
          {FEATURES.evolution && tab('/evolution', 3, '4 Evolution')}
        </nav>
      </header>
      <div className="bricks" />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/scene" replace />} />
          <Route path="/scene" element={<SceneScreen />} />
          <Route path="/fly" element={<FlyScreen />} />
          <Route path="/run/:runId" element={FEATURES.lite ? <LiteRunScreen /> : <RunScreen />} />
          {FEATURES.moments && <Route path="/moment/:momentId" element={<MomentScreen />} />}
          {FEATURES.evolution && <Route path="/evolution/:id?" element={<EvolutionScreen />} />}
        </Routes>
      </main>
    </>
  )
}
