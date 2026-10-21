// Screenshots of every screen at the sizes the wireframes were drawn at (and the Run tab at the extremes), for the
// side-by-side comparison with web/design/*.png:  node e2e/shots.mjs   then   python e2e/compare.py
// Needs the API (python -m fly_mario.api) and the dev server (npm run dev); BASE points at the latter.
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const out = 'screenshots/mine'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const shot = (n, full = true) => page.screenshot({ path: `${out}/${n}.png`, fullPage: full })

// Scene: 1-1 selected
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').waitFor()
await page.waitForFunction(() => [...document.images].every((i) => i.complete))
await page.locator('[data-level="1-1"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await shot('scene')

// Fly: the champion, then the Advanced drawer
await page.getByText('Next: choose the fly').click()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
await page.waitForTimeout(1500)
await shot('fly')
await page.getByText('Advanced: fine-tune').click()
await page.waitForTimeout(300)
await shot('advanced', false)
await page.getByLabel('close').click()

// Run on 1-2 (the champion dies at the Koopa), as in the wireframe
await page.goto(`${base}/scene`)
await page.locator('[data-level="1-2"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await page.getByText('Next: choose the fly').click()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
await page.getByText('▶ Run', { exact: true }).click()
await page.locator('[data-testid=brain-panel]').waitFor({ timeout: 60_000 })
await page.waitForFunction(() => document.querySelector('[data-testid=timeline]')?.getAttribute('aria-label')?.match(/frame [1-9]\d{2,}/))
await shot('run_live', false)
await page.getByRole('button', { name: 'Fast' }).click()
await page.locator('.banner[role=status]').waitFor({ timeout: 600_000 })
await page.waitForTimeout(400)
await shot('run')
for (const [w, h] of [[1280, 720], [2560, 1440]]) {
  await page.setViewportSize({ width: w, height: h })
  await page.waitForTimeout(300)
  await shot(`run_${w}x${h}`)
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  const fit = await page.evaluate(() => ({ stage: document.querySelector('[data-testid=stage]').getBoundingClientRect().toJSON(), banner: document.querySelector('.banner').getBoundingClientRect().bottom, doc: document.documentElement.scrollHeight }))
  console.log(`${w}x${h}: horizontal overflow ${over}px; stage ${Math.round(fit.stage.width)}x${Math.round(fit.stage.height)} (${(fit.stage.width / fit.stage.height).toFixed(3)}), banner bottom ${Math.round(fit.banner)}, page height ${fit.doc}`)
}
await page.setViewportSize({ width: 1440, height: 900 })

// Change & try again
await page.getByText('Rewind 3 s').click()
await page.getByText('Resume from here').waitFor()
await page.waitForTimeout(500)
await shot('retry')

console.log(errors.length ? `page errors: ${errors}` : 'no page errors')
await browser.close()
