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


/** The order things are listed in, per tab (the names are the plug-in names). A type these lists do not name, such as a newly added
 *  plug-in, comes after them in the registry's order. tests/test_web_object_order.py keeps this in step with the registered kinds. */
export const OBJECT_ORDER: Record<string, string[]> = {
  enemies: ['goomba', 'koopa', 'piranha', 'hammer_bro', 'buzzy_beetle', 'podoboo', 'red_koopa'],
  objects: ['pipe', 'step', 'pit', 'qblock', 'usedblock', 'brick', 'ceiling_block'],
  powerups: ['mushroom', 'fire_flower', 'one_up', 'star', 'coin'],
}
const RANK = new Map(Object.values(OBJECT_ORDER).flat().map((n, i) => [n, i]))
export const objectRank = (name: string) => RANK.get(name) ?? RANK.size
export const byObjectOrder = <T extends { name: string }>(l: T[]) => [...l].sort((a, b) => objectRank(a.name) - objectRank(b.name))

/** Columns and buttons in the order the API gives each plug-in (`order`); ties keep the registry's order. */
export const byOrder = <T extends { order: number }>(l: T[]) => [...l].sort((a, b) => a.order - b.order)
