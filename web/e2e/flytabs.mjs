// The Fly tab's grid: every registered object type, split into Enemies / Objects / Power-ups by registry kind, in the display order
// of components/senseUtil.ts (OBJECT_ORDER).
// python tools/e2e_stack.py e2e/flytabs.mjs (from the repo root). Screenshots go to $SHOTS (default screenshots/flytabs).
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const api = process.env.API ?? 'http://127.0.0.1:8010'
const out = process.env.SHOTS ?? 'screenshots/flytabs'
mkdirSync(out, { recursive: true })
const reg = await (await fetch(`${api}/registry`)).json()
const WANT = { Enemies: ['enemy'], Objects: ['terrain', 'obstacle'], 'Power-ups': ['pickup'] }
const ORDER = {   // the display order, by plug-in name
  Enemies: ['goomba', 'koopa', 'piranha', 'hammer_bro', 'buzzy_beetle', 'podoboo', 'red_koopa'],
  Objects: ['pipe', 'step', 'pit', 'qblock', 'usedblock', 'brick', 'ceiling_block'],
  'Power-ups': ['mushroom', 'fire_flower', 'one_up', 'star', 'coin'],
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
await page.goto(`${base}/fly`)
await page.getByRole('tab', { name: 'Enemies' }).waitFor()
assert.equal(await page.getByRole('tab').count(), 3)
let total = 0
for (const [label, kinds] of Object.entries(WANT)) {
  await page.getByRole('tab', { name: label }).click()
  const want = reg.objects.filter((o) => kinds.includes(o.kind)).map((o) => o.label)
  const rows = await page.locator('.sg-row .sg-thing b').allInnerTexts()
  assert.deepEqual([...rows].sort(), [...want].sort(), `${label}: rows are exactly the registered types of those kinds`)
  assert.deepEqual(rows, ORDER[label].map((n) => reg.objects.find((o) => o.name === n).label), `${label}: rows are in the display order`)
  console.log(label + ':', rows.join(' > '))
  total += rows.length
  await page.screenshot({ path: `${out}/fly_${label.toLowerCase().replace('-', '')}.png` })
}
assert.equal(total, reg.objects.length, 'every registered object type shows on some tab')
assert.deepEqual(errors, [])
await browser.close()
console.log('flytabs ok:', total, 'object types over 3 tabs')
