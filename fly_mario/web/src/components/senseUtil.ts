import type { ObjectInfo } from '../api/models'

/** "Looming (the next threat grows)" -> ["Looming", "the next threat grows"]: the registry labels carry both. */
export const splitLabel = (label: string): [string, string] => {
  const m = /^(.*?)\s*\((.*)\)\s*$/.exec(label)
  return m ? [m[1], m[2]] : [label, '']
}

const KIND_ORDER = ['enemy', 'obstacle', 'pickup', 'terrain']
export const byKind = (objects: ObjectInfo[]) =>
  [...objects].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind))


/** Columns and buttons in the order of the wireframes; anything the registry adds later follows, in its own order. */
const SENSE_ORDER = ['looming', 'sour_smell', 'hearing', 'sweet_smell']
const ACTION_ORDER = ['walk', 'steer', 'jump', 'back_up']
const rank = (order: string[], n: string) => (order.includes(n) ? order.indexOf(n) : order.length)
export const bySenseOrder = <T extends { name: string }>(l: T[]) => [...l].sort((a, b) => rank(SENSE_ORDER, a.name) - rank(SENSE_ORDER, b.name))
export const byActionOrder = <T extends { name: string }>(l: T[]) => [...l].sort((a, b) => rank(ACTION_ORDER, a.name) - rank(ACTION_ORDER, b.name))
