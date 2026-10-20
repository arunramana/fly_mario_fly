import type { ObjectInfo } from '../api/models'

/** "Looming (the next threat grows)" -> ["Looming", "the next threat grows"]: the registry labels carry both. */
export const splitLabel = (label: string): [string, string] => {
  const m = /^(.*?)\s*\((.*)\)\s*$/.exec(label)
  return m ? [m[1], m[2]] : [label, '']
}

const KIND_ORDER = ['enemy', 'obstacle', 'pickup', 'terrain']
export const byKind = (objects: ObjectInfo[]) =>
  [...objects].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind))


/** Columns and buttons in the order the API gives each plug-in (`order`); ties keep the registry's order. */
export const byOrder = <T extends { order: number }>(l: T[]) => [...l].sort((a, b) => a.order - b.order)
