// End-to-end against the REAL backend.
//   terminal 1:  python -m fly_mario.api            (http://127.0.0.1:8000)
//   terminal 2:  npm run dev                         (http://localhost:5173)
//   terminal 3:  npm run test:e2e                    (screenshots land in screenshots/)
// Flow: Scene (the level catalogue, then level 1-2, whole level) -> Fly (champion_e1s, Advanced drawer) -> Run (layers,
// toggles, restart) -> dies at the Koopa -> Rewind 3 s -> sour smell stronger -> Resume -> back on the moment screen,
// the new try is in the list. Then the champion on 1-1 with Original dials: the banner names them.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const shot = (n) => page.screenshot({ path: `screenshots/${n}.png`, fullPage: true })
const finish = async (what) => {
  await page.locator('.banner[role=status]').waitFor({ timeout: 600_000 })
  console.log(what, '->', (await page.locator('.banner[role=status]').innerText()).replace(/\s+/g, ' '))
}
const noSideScroll = async (where) =>
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0, `${where}: no horizontal scroll`)

// Scene: the catalogue is 32 stages in order, then the whole game, Lost Levels and Random Stages
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').waitFor()
const ids = await page.locator('[data-level]').evaluateAll((els) => els.map((e) => e.getAttribute('data-level')))
const stages = [1, 2, 3, 4, 5, 6, 7, 8].flatMap((w) => [1, 2, 3, 4].map((s) => `${w}-${s}`))
assert.deepEqual(ids, [...stages, 'full', 'lost_levels', 'random'])
const text = await page.locator('[data-level]').evaluateAll((els) => els.map((e) => e.innerText.replace(/\s+/g, ' ')))
assert.match(text[32], /Whole game/); assert.match(text[33], /Lost Levels/); assert.match(text[34], /Random Stages/)
assert.match(text[5], /2-2 Water/, '2-2 is the water stage'); assert.match(text[3], /1-4 Castle/)
await page.waitForFunction(() => [...document.querySelectorAll('.thumb img')].every((i) => i.complete && i.naturalWidth > 0), null, { timeout: 120_000 })
await noSideScroll('scene')
// choosing a level sets it for the Fly page and the run
await page.locator('[data-level="1-2"]').click()
assert.equal(await page.locator('[data-level="1-2"]').getAttribute('aria-pressed'), 'true')
await page.getByRole('button', { name: 'Whole level' }).click()
await shot('1-scene')

// Fly: the champion
await page.getByText('Next: choose the fly').click()
await page.getByText('Scene: 1-2').waitFor()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
await page.getByLabel('Home').isChecked()
await shot('2-fly')
await page.getByText('Advanced: fine-tune').click()
await page.getByRole('dialog', { name: 'Fine-tune this fly' }).waitFor()
await shot('2b-advanced')
await page.getByLabel('close').click()

// Run
await page.getByText('▶ Run', { exact: true }).click()
await page.getByText('◆ Save this moment').waitFor()
await page.locator('[data-testid=picture]').waitFor()
await page.locator('[data-testid=brain-panel]').waitFor({ timeout: 60_000 })
await page.waitForFunction(() => document.querySelector('[data-testid=timeline]')?.getAttribute('aria-label')?.match(/frame [1-9]\d*/))
await page.getByText('◆ Save this moment').click()
await page.locator('[data-testid=moment-mark]').first().waitFor()
// "Show senses" and "Show brain" flip layers that are always there
await page.locator('[data-testid=overlay]').first().waitFor({ timeout: 60_000 })
const overlay = page.locator('[data-testid=overlay]').first()
assert.equal(await overlay.evaluate((e) => getComputedStyle(e).visibility), 'visible')
await page.getByLabel('Show senses').uncheck()
assert.equal(await overlay.evaluate((e) => getComputedStyle(e).visibility), 'hidden')
await page.getByLabel('Show senses').check()
await page.getByLabel('Show brain').uncheck()
assert.match(await page.locator('[data-testid=stage]').getAttribute('class'), /nobrain/)
await page.getByLabel('Show brain').check()
// the picture fits the window and keeps its shape
const box = await page.locator('[data-testid=stage]').boundingBox()
assert.ok(Math.abs(box.width / box.height - 16 / 9) < 0.02, 'the run picture keeps 16:9')
await noSideScroll('run')
await page.getByRole('button', { name: 'Fast' }).click()
await shot('3a-running')
await finish('first run')
const banner = page.locator('.banner[role=status]')
assert.equal(await banner.getAttribute('data-outcome'), 'died')
assert.match(await banner.innerText(), /Koopa/, 'the fly dies at the Koopa')
await page.locator('[data-testid=death-mark]').waitFor()
await shot('3b-died')

// Restart: the same fly and scene, a new run
const firstUrl = page.url()
await page.getByLabel('restart').click()
await page.waitForFunction((u) => location.href !== u, firstUrl)
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
await finish('restarted run')
assert.match(await page.locator('.banner[role=status]').innerText(), /Koopa/, 'the restart is the same fly on the same scene')

// Rewind -> moment screen
await page.getByText('Rewind 3 s').click()
await page.getByText('Resume from here').waitFor()
await page.getByText('Senses on things here').waitFor()
await page.locator('[data-testid=picture]').waitFor()
await shot('4-moment')
const triesBefore = await page.getByTestId('try').count()

// Sour smell stronger, resume
await page.getByLabel('Sourness').fill('1000')
await shot('5-sour-stronger')
await page.getByText('Resume from here').click()
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
await finish('resumed run')
await shot('6-resumed')
await page.getByText('Back to the moment').click()
await page.getByText('Tries from this moment').waitFor()
await page.getByTestId('try').first().waitFor()
assert.equal(await page.getByTestId('try').count(), triesBefore + 1, 'the new try is in the list')
console.log('tries:', await page.getByTestId('try').allInnerTexts())
await shot('7-tries')

// Dials: the champion with its ORIGINAL dials on 1-1 (the banner says which dials the run used)
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await page.getByText('Next: choose the fly').click()
await page.getByText('Scene: 1-1').waitFor()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
assert.equal(await page.getByRole('button', { name: 'Tuned' }).getAttribute('aria-pressed'), 'true', 'Tuned is the default')
await page.getByText('Advanced: fine-tune').click()
await page.getByRole('dialog', { name: 'Fine-tune this fly' }).waitFor()
assert.ok(await page.locator('.knob[data-tuned=true]').count() > 0, 'knobs evolution moved are marked')
assert.ok(await page.getByTestId('original-tick').count() > 0, 'each slider has a tick at its original position')
await page.getByLabel('close').click()
await page.getByRole('button', { name: 'Original' }).click()
assert.equal(await page.getByRole('button', { name: 'Original' }).getAttribute('aria-pressed'), 'true')
await shot('8-fly-original')
await page.getByText('▶ Run', { exact: true }).click()
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
await finish('original-dials run on 1-1')
assert.equal(await page.locator('.banner[role=status]').getAttribute('data-dials'), 'original')
assert.match(await page.locator('.banner[role=status]').innerText(), /Dials: Original/, 'the banner says Original')
await shot('9-original-banner')

assert.deepEqual(errors, [], 'no page errors')
await browser.close()
console.log('E2E OK')
