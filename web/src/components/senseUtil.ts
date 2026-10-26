import type { ObjectInfo } from '../api/models'

/** "Looming (the next threat grows)" -> ["Looming", "the next threat grows"]: the registry labels carry both. */
export const splitLabel = (label: string): [string, string] => {
  const m = /^(.*?)\s*\((.*)\)\s*$/.exec(label)
  return m ? [m[1], m[2]] : [label, '']
}

/** The sub-tabs of the sense grid: each groups registry kinds; a kind that no tab lists falls into the last one. */
export const OBJECT_TABS: { id: string; label: string; kinds: string[] }[] = [
  { id: 'enemies', label: 'Enemies', kinds: ['enemy'] },
  { id: 'objects', label: 'Objects', kinds: ['terrain', 'obstacle'] },
  { id: 'powerups', label: 'Power-ups', kinds: ['pickup'] },
]
export const tabOf = (o: ObjectInfo) =>
  (OBJECT_TABS.find((t) => t.kinds.includes(o.kind)) ?? OBJECT_TABS[OBJECT_TABS.length - 1]).id


/** Columns and buttons in the order the API gives each plug-in (`order`); ties keep the registry's order. */
export const byOrder = <T extends { order: number }>(l: T[]) => [...l].sort((a, b) => a.order - b.order)
