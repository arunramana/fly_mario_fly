// End-to-end for the video export against the REAL backend: Run -> "Download video" -> preview stills appear, and
// nothing is rendered until "Render video" is pressed (RENDER=1 also presses it and waits for the download link).
//   python -m fly_mario.api --port 8765 ;  VITE_API_URL=http://127.0.0.1:8765 npm run dev -- --port 5765
//   BASE=http://localhost:5765 npm run test:e2e:video
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
mkdirSync('screenshots', { recursive: true })

await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await page.getByText('Next: choose the fly').click()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
await page.getByText('▶ Run', { exact: true }).click()
await page.getByText('◆ Save this moment').waitFor()
await page.getByRole('button', { name: 'Fast' }).click()
await page.locator('.banner[role=status]').waitFor({ timeout: 600_000 })

const open = page.getByRole('button', { name: 'Download video' })
assert.equal(await open.isEnabled(), true, 'Download video is available once the run has ended')
await open.click()
await page.getByTestId('video-export').waitFor()
await page.getByRole('button', { name: 'Make preview stills' }).click()
await page.waitForFunction(() => document.querySelectorAll('[data-testid=video-still]').length >= 2 &&
  [...document.querySelectorAll('[data-testid=video-still]')].every((i) => i.complete && i.naturalWidth > 0), null, { timeout: 600_000 })
const n = await page.getByTestId('video-still').count()
console.log('stills shown:', n)
assert.ok(n >= 2 && n <= 3, '2-3 preview stills')
assert.equal(await page.getByTestId('video-download').count(), 0, 'nothing is rendered before the user asks')
await page.getByRole('button', { name: 'Render video' }).waitFor()
await page.screenshot({ path: 'screenshots/video-stills.png', fullPage: true })

if (process.env.RENDER) {
  await page.getByRole('button', { name: 'Render video' }).click()
  await page.getByTestId('video-rendering').waitFor()
  await page.getByTestId('video-download').waitFor({ timeout: 900_000 })
  const href = await page.getByTestId('video-download').getAttribute('href')
  const res = await fetch(href)
  assert.equal(res.status, 200)
  assert.equal(res.headers.get('content-type'), 'video/mp4')
  console.log('video ->', href, (await res.arrayBuffer()).byteLength, 'bytes')
  await page.screenshot({ path: 'screenshots/video-done.png', fullPage: true })
}

assert.deepEqual(errors, [], 'no page errors')
await browser.close()
console.log('E2E VIDEO OK')
