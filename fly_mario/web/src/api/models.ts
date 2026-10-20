// Short names for the generated schema (types.ts, from `npm run gen:types`). No shapes are declared here.
import type { components } from './types'

type S = components['schemas']

export type Box = S['Box']
export type KnobUI = S['KnobUI']
export type ObjectInfo = S['ObjectInfo']
export type SenseInfo = S['SenseInfo']
export type ActionInfo = S['ActionInfo']
export type ShapeInfo = S['ShapeInfo']
export type SceneModifierInfo = S['SceneModifierInfo']
export type Registry = S['RegistryInfo']
export type Scene = S['SceneDTO']
export type Fly = S['FlyDTO']
export type LevelInfo = S['LevelInfo']
export type RunRequest = S['RunRequestDTO']
export type RunResult = S['RunResultDTO']
export type RunSummary = S['RunSummary']
export type MomentSummary = S['MomentSummary']
export type Try = S['TryDTO']
export type OverlayItem = S['OverlayItem']
export type ObjectOnScreen = S['ObjectOnScreen']
export type FrameEvent = S['FrameEvent']
export type MomentEvent = S['MomentEvent']
export type EndEvent = S['EndEvent']
export type StateEvent = S['StateEvent']
export type ErrorEvent = S['ErrorEvent']
export type RunEvent = S['RunEvent']
export type ClientMessage = S['ClientMessage']

/** A run's live connection. Events arrive through `onEvent`; the rest are the client messages of the API. */
export interface RunStream {
  onEvent(cb: (e: RunEvent) => void): void
  play(): void
  pause(): void
  step(): void
  setSpeed(multiplier: number): void
  close(): void
}
