// End-to-end for the polish round, against the REAL backend: python tools/e2e_stack.py e2e/polish.mjs (from the repo root).
//  1. Scene: "Next" is disabled until a level, a test scene and a start are chosen, and says what is missing.
//  2. Run: a blank fly never moves, and the run ends "stuck" ("Mario got stuck at x ...").
//  3. Montage: a 3-generation tiny evolution gives a montage with 3 clips whose length is the sum of the clips / speed.
// Screenshots of Scene and Fly (drawer open) at 1280x720 and 1920x1080 go to screenshots/polish/.
import assert from 'node:assert/strict'
import { mkdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const api = process.env.API ?? 'http://127.0.0.1:8010'
const out = 'screenshots/polish'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))

const SIZES = [[1280, 720], [1920, 1080]]
const shoot = async (name) => {
  for (const [width, height] of SIZES) {
    await page.setViewportSize({ width, height })
    await page.waitForTimeout(400)
    await page.screenshot({ path: `${out}/${name}_${width}x${height}.png` })
    const m = await page.evaluate(() => ({
      x: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      y: document.documentElement.scrollHeight - document.documentElement.clientHeight,
    }))
    assert.ok(m.x <= 0 && m.y <= 0, `${name} at ${width}x${height}: the page scrolls (${JSON.stringify(m)})`)
  }
  await page.setViewportSize({ width: 1440, height: 900 })
}
const json = async (path, init) => {
  const r = await fetch(api + path, init)
  const body = await r.json()
  assert.ok(r.ok, `${path}: ${r.status} ${JSON.stringify(body)}`)
  return body
}

// ---- 1. Scene: Next is disabled until everything is chosen --------------------------------------------------------------
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').waitFor()
await page.getByRole('button', { name: 'Whole level' }).waitFor()
const next = page.getByRole('button', { name: /Next: choose the fly/ })
const missing = page.getByTestId('scene-missing')
assert.equal(await next.isDisabled(), true, 'nothing chosen: Next is disabled')
assert.match(await missing.innerText(), /a level.*a test scene.*a start/)
assert.equal(await page.getByText('Place an object').count(), 0, '"Place an object" is gone')
assert.deepEqual((await page.locator('.chip.test').allInnerTexts()).sort(), ['No enemies', 'Whole level'], 'the test scenes are Whole level and No enemies only')
assert.deepEqual(await page.locator('input[name=start]').evaluateAll((e) => e.map((i) => i.parentElement.innerText.trim())), ['the level start', 'a saved moment'], 'Start from: the level start or a saved moment')
assert.equal(await page.locator('[data-level][aria-pressed=true]').count(), 0, 'no level looks chosen before it is clicked')
await page.locator('[data-level="1-1"]').click()
assert.equal(await next.isDisabled(), true)
assert.match(await missing.innerText(), /a test scene.*a start/)
assert.doesNotMatch(await missing.innerText(), /a level/)
await page.getByRole('button', { name: 'Whole level' }).click()
assert.equal(await next.isDisabled(), true)
assert.match(await missing.innerText(), /^Still to choose: a start\.$/)
await shoot('1-scene_missing')
await page.getByLabel('the level start').check()
assert.equal(await next.isDisabled(), false, 'level, test scene and start chosen: Next is enabled')
await page.locator('[data-level="1-2"]').click()                   // a new level asks for its start again
assert.equal(await next.isDisabled(), true)
assert.match(await missing.innerText(), /a start/)
await page.getByLabel('the level start').check()
await page.locator('[data-level="1-1"]').click()
await page.getByLabel('the level start').check()
assert.equal(await next.isDisabled(), false)
await shoot('1-scene')
const rects = await page.evaluate(() => ({
  grid: document.querySelector('.level-grid').getBoundingClientRect().width,
  side: document.querySelector('.scene > aside').getBoundingClientRect().width,
  sideScrolls: (() => { const a = document.querySelector('.scene > aside'); return a.scrollHeight > a.clientHeight })(),
}))
console.log('scene widths (1440): grid', Math.round(rects.grid), 'sidebar', Math.round(rects.side), 'sidebar scrolls', rects.sideScrolls)
assert.ok(rects.side > rects.grid * 0.6, 'the sidebar has real width')

// ---- 2. Fly: the drawer slides in from the left, wide ----------------------------------------------------------------------
await next.click()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByText('champion_e1s · 6 senses on').waitFor()
// the brain map of the fly shows the brain (not an empty box)
await page.waitForFunction(() => { const i = document.querySelector('.brainmap img'); return i && i.complete && i.naturalWidth > 0 }, null, { timeout: 120_000 })
console.log('brain map shows an image')
// every row of the grid shows its picture (a real image, loaded), not an empty square
await page.waitForFunction(() => [...document.querySelectorAll('.sg-row')].every((r) => {
  const i = r.querySelector('img[data-testid=object-icon]'); return i && i.complete && i.naturalWidth > 0
}), null, { timeout: 300_000 })
const rowsN = await page.locator('.sg-row').count()
assert.ok(rowsN > 0 && (await page.locator('.sg-row img[data-testid=object-icon]').count()) === rowsN, 'every Fly-grid row shows an image')
console.log('Fly grid: rows with an icon image', rowsN, 'of', rowsN)
await page.screenshot({ path: `${out}/2-fly_grid_icons_1440x900.png` })
await shoot('2-fly')
await page.getByText('Advanced: fine-tune').click()
const drawer = page.getByRole('dialog', { name: 'Fine-tune this fly' })
await drawer.waitFor()
await page.waitForTimeout(500)
for (const [width, height] of SIZES) {
  await page.setViewportSize({ width, height })
  await page.waitForTimeout(400)
  const b = await drawer.boundingBox()
  assert.ok(b.x <= 1, `the drawer is on the left (x ${b.x})`)
  assert.ok(b.width >= Math.max(0.45 * width, 560) - 2, `the drawer is wide enough (${b.width}px at ${width})`)
  const clipped = await drawer.evaluate((d) => [...d.querySelectorAll('.ends span, .knob-name, .reset')]
    .filter((e) => e.scrollWidth > e.clientWidth + 1 || e.getBoundingClientRect().right > d.getBoundingClientRect().right + 1).length)
  assert.equal(clipped, 0, `every label and end label is fully inside the drawer at ${width}x${height}`)
  await page.screenshot({ path: `${out}/2-fly_drawer_${width}x${height}.png` })
  const m = await page.evaluate(() => document.documentElement.scrollHeight - document.documentElement.clientHeight)
  assert.ok(m <= 0, 'the page does not scroll with the drawer open')
}
await page.setViewportSize({ width: 1440, height: 900 })
await page.getByLabel('close').click()

// ---- 3. a blank fly never moves: the run ends "stuck" -------------------------------------------------------------------------
await page.getByLabel('preset').selectOption('blank')
await page.getByText('blank · 0 senses on').waitFor()
await page.getByText('▶ Run', { exact: true }).click()
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
const banner = page.locator('.banner[role=status]')
await banner.waitFor({ timeout: 300_000 })
assert.equal(await banner.getAttribute('data-outcome'), 'stuck', 'a run that never moves ends stuck')
assert.match(await banner.innerText(), /Mario got stuck at x \d+/)
console.log('blank fly ->', (await banner.innerText()).replace(/\s+/g, ' '))

// ---- 4. montage of a 3-generation tiny evolution -----------------------------------------------------------------------------
const view = await json('/flies/champion_e1s')
delete view.dials
const evo = await json('/jobs/evolve', { method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ fly: view, dials: 'tuned', level: '1-1', generations: 3, population: 4, train_n: 2, workers: 0 }) })
console.log('evolution', evo.id)
let job
for (let i = 0; i < 1800; i++) {
  job = await json(`/jobs/${evo.id}`)
  if (['finished', 'failed', 'cancelled'].includes(job.status)) break
  await new Promise((r) => setTimeout(r, 2000))
}
assert.equal(job.status, 'finished', job.error)
assert.equal(job.progress.bars.length, 3, 'three generations')

// while it ran the montage was refused; the page offers speeds 1x 2x 4x with 2x pressed
await page.goto(`${base}/evolution/${evo.id}`)
await page.getByTestId('montage').waitFor()
const speeds = page.getByRole('group', { name: 'montage speed' })
assert.deepEqual(await speeds.getByRole('button').allInnerTexts(), ['1×', '2×', '4×'])
assert.equal(await speeds.getByRole('button', { name: '2×' }).getAttribute('aria-pressed'), 'true', '2x is the default')
assert.equal(await page.getByRole('button', { name: 'Download montage' }).isDisabled(), false)

const vid = await json('/videos', { method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ export: 'montage', job_id: evo.id, speed: 2 }) })
let v
for (let i = 0; i < 1800; i++) {
  v = await json(`/videos/${vid.id}`)
  if (['finished', 'failed', 'cancelled'].includes(v.status)) break
  await new Promise((r) => setTimeout(r, 2000))
}
assert.equal(v.status, 'finished', v.error)
const data = (process.env.FLY_MARIO_FLY_DATA ?? process.env.FLY_MARIO_DATA)
const info = JSON.parse(readFileSync(join(data, 'videos', vid.id, 'info.json'), 'utf8'))
const game = info.clips.map((c) => c.game_frames)
const expected = info.clips.reduce((s, c) => s + c.output_frames, 0) / 60
console.log('montage: clips', info.clips.length, 'game frames', game, 'outcomes', info.clips.map((c) => c.outcome),
  'duration', info.duration_s, 's, sum of clips / speed', (game.reduce((a, b) => a + b, 0) / 2 / 60).toFixed(2), 's + holds -> expected', expected.toFixed(2), 's')
assert.equal(v.clips, 3)
assert.equal(info.clips.length, job.progress.bars.length, 'one clip per generation')
assert.ok(Math.abs(info.duration_s - expected) < 0.1, 'duration = sum of the clips / speed (+ the hold on each last picture)')
assert.ok(info.clips.every((c) => ['flag', 'died', 'stuck', 'timeout'].includes(c.outcome)))
assert.deepEqual(errors, [], 'no page errors')
await browser.close()
console.log('POLISH E2E OK')
