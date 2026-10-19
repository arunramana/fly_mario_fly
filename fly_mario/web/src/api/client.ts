// The only module components import for data. S7b swaps `api` for an HTTP implementation.
import type {
  FlyConfig, LevelInfo, MomentDetail, MomentSummary, Registry, RunRequest, RunResult, RunStream,
} from './types'
import { mockApi } from './mock'

export interface Api {
  getRegistry(): Promise<Registry>
  getLevels(): Promise<LevelInfo[]>
  getFly(name: string): Promise<FlyConfig>
  saveFly(fly: FlyConfig): Promise<FlyConfig>
  startRun(req: RunRequest): Promise<{ run_id: string }>
  runStream(runId: string): RunStream
  saveMoment(runId: string, frame: number, name: string, auto?: boolean): Promise<MomentSummary>
  getMoments(): Promise<MomentSummary[]>
  getMoment(id: string): Promise<MomentDetail>
  getTries(momentId: string): Promise<RunResult[]>
  resumeFromMoment(momentId: string, fly: FlyConfig): Promise<{ run_id: string }>
}

export const api: Api = mockApi
