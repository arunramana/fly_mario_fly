import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useDraft } from './state'
import SceneScreen from './screens/SceneScreen'
import FlyScreen from './screens/FlyScreen'
import RunScreen from './screens/RunScreen'
import MomentScreen from './screens/MomentScreen'

export default function App() {
  const { lastRunId } = useDraft()
  return (
    <>
      <header className="app-header">
        <h1>FLY MARIO</h1>
        <nav>
          <NavLink to="/scene">1 Scene</NavLink>
          <NavLink to="/fly">2 Fly</NavLink>
          {lastRunId && <NavLink to={`/run/${lastRunId}`}>3 Run</NavLink>}
        </nav>
      </header>
      <div className="bricks" />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/scene" replace />} />
          <Route path="/scene" element={<SceneScreen />} />
          <Route path="/fly" element={<FlyScreen />} />
          <Route path="/run/:runId" element={<RunScreen />} />
          <Route path="/moment/:momentId" element={<MomentScreen />} />
        </Routes>
      </main>
    </>
  )
}
