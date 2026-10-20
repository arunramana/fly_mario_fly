// End-to-end against the REAL backend.
//   terminal 1:  python -m fly_mario.api            (http://127.0.0.1:8000)
//   terminal 2:  npm run dev                         (http://localhost:5173)
//   terminal 3:  npm run test:e2e                    (screenshots land in screenshots/)
// Flow: Scene (level 1-2, whole level) -> Fly (champion_e1s) -> Run -> dies at the Koopa -> Rewind 3 s -> sour smell
// stronger -> Resume -> back on the moment screen, the new try is in the list.
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

// Scene: level 1-2, whole level
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').waitFor()
assert.match(await page.locator('[data-level="1-3"]').innerText(), /\? objects/, 'an unscanned level shows "?"')
await page.locator('[data-level="1-2"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await shot('1-scene')

// Fly: the champion
await page.getByText('Next ▶').click()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('fly name').and(page.locator('[value="champion_e1s"]')).waitFor()
await page.getByText('Advanced').click()
await shot('2-fly')

// Run
await page.getByText('Run ▶').click()
await page.getByText('Save this moment').waitFor()
await page.locator('[data-testid=picture]').waitFor()
await page.waitForFunction(() => document.body.innerText.match(/frame [1-9]\d*/))
await page.getByText('Save this moment').click()
await page.locator('[data-testid=moment-mark]').first().waitFor()
// "Show senses" flips a separate layer
const overlay = page.locator('[data-testid=overlay]')
assert.equal(await overlay.evaluate((e) => getComputedStyle(e).visibility), 'visible')
await page.getByLabel('Show senses').uncheck()
assert.equal(await overlay.evaluate((e) => getComputedStyle(e).visibility), 'hidden')
await page.getByLabel('Show senses').check()
await page.getByLabel('Show brain').uncheck()
assert.equal(await page.locator('[data-testid=brain-panel]').count(), 0)
await page.getByLabel('Show brain').check()
await page.getByLabel('speed').selectOption({ label: 'max' })
await shot('3a-running')
await finish('first run')
const banner = page.locator('.banner[role=status]')
assert.equal(await banner.getAttribute('data-outcome'), 'died')
assert.match(await banner.innerText(), /Koopa/, 'the fly dies at the Koopa')
await page.locator('[data-testid=death-mark]').waitFor()
await shot('3b-died')

// Rewind -> moment screen
await page.getByText('Rewind 3 s').click()
await page.getByText('Resume from here').waitFor()
await page.getByText('Senses on what is on screen').waitFor()
await page.locator('[data-testid=picture]').waitFor()
await shot('4-moment')
const triesBefore = await page.getByTestId('try').count()

// Sour smell stronger, resume
const sour = page.getByLabel('Sourness')
await sour.fill('1000')
await shot('5-sour-stronger')
await page.getByText('Resume from here').click()
await page.getByText('Save this moment').waitFor()
await page.getByLabel('speed').selectOption({ label: 'max' })
await finish('resumed run')
await shot('6-resumed')
await page.getByText('Back to the moment').click()
await page.getByText('Tries from this moment').waitFor()
await page.getByTestId('try').first().waitFor()
assert.equal(await page.getByTestId('try').count(), triesBefore + 1, 'the new try is in the list')
console.log('tries:', await page.getByTestId('try').allInnerTexts())
await shot('7-tries')

assert.deepEqual(errors, [], 'no page errors')
await browser.close()
console.log('E2E OK')
