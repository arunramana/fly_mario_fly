// End-to-end against the REAL backend, run through `python tools/e2e_stack.py` (from the repo root). That starts a private
// API (its own flies folder, FLY_MARIO_FLY_FLIES_DIR) and vite, runs this script and cleans up; nothing lands in configs/flies/.
// Or by hand: python -m fly_mario_fly.api  ;  npm run dev  ;  npm run test:e2e   (BASE points at the dev server).
// Flow: Scene -> Fly (champion) -> Run (dies at the Koopa) -> Download video (an .mp4 file is saved) -> Rewind 3 s ->
// sour smell stronger -> Resume -> Original dials run -> Evolution: Test this fly, a tiny evolution (graph, parameters,
// montage plays, Download montage saves a file, Save as fly -> in the Fly presets).
// Every screen is photographed at 1280x720, 1920x1080 and 2560x1440 and must not scroll the page (screenshots/lean/).
import assert from 'node:assert/strict'
import { mkdirSync, readFileSync, statSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const out = 'screenshots/lean'
mkdirSync(`${out}/downloads`, { recursive: true })
const browser = await chromium.launch()
const home = { width: 1440, height: 900 }
const page = await browser.newPage({ viewport: home, acceptDownloads: true })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const finish = async (what) => {
  await page.locator('.banner[role=status]').waitFor({ timeout: 600_000 })
  console.log(what, '->', (await page.locator('.banner[role=status]').innerText()).replace(/\s+/g, ' '))
}

// Photograph the screen as it is at the three window sizes; the page itself must not scroll at any of them.
const SIZES = [[1280, 720], [1920, 1080], [2560, 1440]]
const fits = async (name) => {
  for (const [width, height] of SIZES) {
    await page.setViewportSize({ width, height })
    await page.waitForTimeout(350)
    const m = await page.evaluate(() => ({
      x: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      y: document.documentElement.scrollHeight - document.documentElement.clientHeight,
      bodyY: document.body.scrollHeight - innerHeight,
    }))
    await page.screenshot({ path: `${out}/${name}_${width}x${height}.png` })
    assert.ok(m.x <= 0 && m.y <= 0 && m.bodyY <= 0, `${name} at ${width}x${height}: the page scrolls (${JSON.stringify(m)})`)
  }
  await page.setViewportSize(home)
}

// A button that downloads: the file must really arrive, and be an mp4.
const downloads = async (name, click) => {
  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 900_000 }), click()])
  const path = `${out}/downloads/${name}.mp4`
  await dl.saveAs(path)
  const size = statSync(path).size
  const head = readFileSync(path).subarray(4, 8).toString('latin1')
  assert.ok(size > 50_000 && head === 'ftyp', `${name}: a real mp4 was saved (${size} bytes, header ${head})`)
  console.log('downloaded', dl.suggestedFilename(), size, 'bytes')
}

// Scene: the catalogue is 32 stages in order, then the whole game, Lost Levels and Random Stages
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').waitFor()
const ids = await page.locator('[data-level]').evaluateAll((els) => els.map((e) => e.getAttribute('data-level')))
const stages = [1, 2, 3, 4, 5, 6, 7, 8].flatMap((w) => [1, 2, 3, 4].map((s) => `${w}-${s}`))
assert.deepEqual(ids, [...stages, 'full', 'lost_levels', 'random'])
await page.waitForFunction(() => [...document.querySelectorAll('.thumb img')].every((i) => i.complete && i.naturalWidth > 0), null, { timeout: 120_000 })
assert.equal(await page.title(), 'fly_mario_fly')
assert.equal(await page.locator('.brand').innerText(), 'fly_mario_fly')
assert.deepEqual((await page.locator('.app-header nav a').allInnerTexts()).map((t) => t.replace(/ ✓$/, '')), ['1 Scene', '2 Fly', '3 Run', '4 Evolution'])
await page.locator('[data-level="1-2"]').click()
assert.equal(await page.locator('[data-level="1-2"]').getAttribute('aria-pressed'), 'true')
await page.getByRole('button', { name: 'Whole level' }).click()
await page.getByLabel('the level start').check()
await fits('1-scene')

// Fly: the champion; the Evolve / Test controls are no longer here
await page.getByText('Next: choose the fly').click()
await page.getByText('Scene: 1-2').waitFor()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
assert.equal(await page.getByTestId('evolve-panel').count(), 0, 'no Evolve controls on the Fly tab')
await page.waitForTimeout(1200)
await fits('2-fly')
await page.getByText('Advanced: fine-tune').click()
await page.getByRole('dialog', { name: 'Fine-tune this fly' }).waitFor()
await page.screenshot({ path: `${out}/2b-advanced_1440x900.png` })
await page.getByLabel('close').click()

// Run
await page.getByText('▶ Run', { exact: true }).click()
await page.getByText('◆ Save this moment').waitFor()
await page.locator('[data-testid=picture]').waitFor()
await page.locator('[data-testid=brain-panel]').waitFor({ timeout: 60_000 })
await page.waitForFunction(() => document.querySelector('[data-testid=timeline]')?.getAttribute('aria-label')?.match(/frame [1-9]\d*/))
await page.getByText('◆ Save this moment').click()
await page.locator('[data-testid=moment-mark]').first().waitFor()
await page.locator('[data-testid=overlay]').first().waitFor({ timeout: 60_000 })
const overlay = page.locator('[data-testid=overlay]').first()
assert.equal(await overlay.evaluate((e) => getComputedStyle(e).visibility), 'visible')
await page.getByLabel('Show senses').uncheck()
assert.equal(await overlay.evaluate((e) => getComputedStyle(e).visibility), 'hidden')
await page.getByLabel('Show senses').check()
await page.getByLabel('Show brain').uncheck()
assert.match(await page.locator('[data-testid=stage]').getAttribute('class'), /nobrain/)
await page.getByLabel('Show brain').check()
const box = await page.locator('[data-testid=stage]').boundingBox()
assert.ok(Math.abs(box.width / box.height - 16 / 9) < 0.02, 'the run picture keeps 16:9')
assert.equal(await page.getByRole('button', { name: 'Download video' }).isDisabled(), true, 'no video until the run has ended')
await page.getByRole('button', { name: 'Fast' }).click()
await finish('first run')
const banner = page.locator('.banner[role=status]')
assert.equal(await banner.getAttribute('data-outcome'), 'died')
assert.match(await banner.innerText(), /Died at x \d+ · Koopa/, 'the fly dies at the Koopa')
await page.locator('[data-testid=death-mark]').waitFor()
await fits('3-run')
// the picture scales with the window and keeps its shape
for (const [width, height] of SIZES) {
  await page.setViewportSize({ width, height })
  await page.waitForTimeout(250)
  const b = await page.locator('[data-testid=stage]').boundingBox()
  assert.ok(Math.abs(b.width / b.height - 16 / 9) < 0.02 && b.y + b.height <= height, `run picture fits ${width}x${height}`)
}
await page.setViewportSize(home)

// Download video: one click renders (a progress bar shows) and the browser saves an mp4
await downloads('run', async () => {
  await page.getByRole('button', { name: 'Download video' }).click()
  await page.getByTestId('download-progress').waitFor({ timeout: 30_000 })
})
await page.getByTestId('download-done').waitFor({ timeout: 60_000 })
assert.equal(await page.getByText('Make preview stills').count(), 0, 'no stills step any more')

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
await fits('4-moment')
const triesBefore = await page.getByTestId('try').count()

// Sour smell stronger, resume
await page.getByLabel('Sourness').fill('1000')
await page.getByText('Resume from here').click()
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
await finish('resumed run')
await page.getByText('Back to the moment').click()
await page.getByText('Tries from this moment').waitFor()
await page.getByTestId('try').first().waitFor()
assert.equal(await page.getByTestId('try').count(), triesBefore + 1, 'the new try is in the list')

// Dials: the champion with its ORIGINAL dials on 1-1 (the banner says which dials the run used)
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await page.getByLabel('the level start').check()
await page.getByText('Next: choose the fly').click()
await page.getByText('Scene: 1-1').waitFor()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
assert.equal(await page.getByRole('button', { name: 'Tuned' }).getAttribute('aria-pressed'), 'true', 'Tuned is the default')
await page.getByRole('button', { name: 'Original' }).click()
await page.getByText('▶ Run', { exact: true }).click()
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
await finish('original-dials run on 1-1')
assert.equal(await page.locator('.banner[role=status]').getAttribute('data-dials'), 'original')

// Evolution tab: Test this fly (champion, 1-1): Original vs Tuned out of 10
await page.getByRole('link', { name: '4 Evolution' }).click()
await page.getByTestId('evolve-panel').waitFor()
assert.equal(await page.getByRole('tab').count(), 0, 'no Runs/Flies/Scenes/Videos sub-tabs')
assert.match(await page.getByLabel('evolve fly').innerText(), /champion_e1s \(from the Fly tab\)/)   // the fly just run
await page.getByText('Test this fly (10 starts)').click()
await page.getByTestId('test-headline').waitFor({ timeout: 900_000 })
const headline = await page.getByTestId('test-headline').innerText()
console.log('test ->', headline)
assert.match(headline, /Original \d+\/10 · Tuned 10\/10/, 'the test summary names Original and Tuned')

// A tiny evolution: 2 generations, a small search
await page.getByLabel('generations').selectOption('2')
await page.getByLabel('quick try').check()
await page.getByRole('button', { name: 'Evolve', exact: true }).click()
await page.getByTestId('evolution').waitFor()
await page.getByTestId('evo-progress').waitFor()
await fits('5-evolution-running')
await page.waitForFunction(() => document.querySelectorAll('[data-testid=gen-bar]').length === 2, null, { timeout: 1_800_000 })
await page.locator('[data-testid=evolution][data-status=finished]').waitFor({ timeout: 900_000 })
assert.equal(await page.getByTestId('gen-bar').count(), 2, 'two generations, two bars (best + average)')
const changes = await page.getByTestId('change').allInnerTexts()
assert.ok(changes.length > 0, 'the parameters being evolved are listed')
assert.ok(changes.every((t) => !/\d/.test(t.replace(/\bx\b/g, ''))), `parameters are words, never numbers: ${changes}`)
console.log('parameters:', changes.map((t) => t.replace(/\s+/g, ' ')))
assert.equal(await page.getByTestId('evolutions-list').getByTestId('job-row').count() >= 1, true, 'the evolution is listed')

// Montage: press Download montage -> progress -> a file arrives, and it plays in the page
assert.equal(await page.getByTestId('montage-video').count(), 0, 'not rendered until asked for')
await downloads('montage', async () => {
  await page.getByRole('button', { name: 'Download montage' }).click()
  await page.getByTestId('download-progress').waitFor({ timeout: 30_000 })
})
const player = page.getByTestId('montage-video')
await player.waitFor({ timeout: 60_000 })
await page.waitForFunction(() => { const v = document.querySelector('[data-testid=montage-video]'); return v && v.readyState >= 2 && v.duration > 1 }, null, { timeout: 60_000 })
await player.evaluate((v) => v.play())
await page.waitForFunction(() => document.querySelector('[data-testid=montage-video]').currentTime > 0.3, null, { timeout: 30_000 })
console.log('montage plays in the page')

// Save as fly -> appears in the Fly tab's presets
await page.getByLabel('evolved fly name').fill('e2e_evolved')
await page.getByRole('button', { name: 'Save as fly' }).click()
await page.getByTestId('saved-as').waitFor()
await fits('6-evolution')
await page.getByRole('link', { name: '2 Fly' }).click()
await page.getByLabel('preset').waitFor()
assert.ok((await page.getByLabel('preset').locator('option').allInnerTexts()).includes('e2e_evolved'), 'the saved fly is in the Fly presets')

assert.deepEqual(errors, [], 'no page errors')
await browser.close()
console.log('E2E OK')
