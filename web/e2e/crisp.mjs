// Crisp icons, against the REAL backend: python tools/e2e_stack.py e2e/crisp.mjs (from the repo root).
// At deviceScaleFactor 1, 1.25, 1.5 and windows 1280x720, 1920x1080: every Fly-grid icon is drawn at a whole multiple of its
// natural size in device pixels (img width*dpr and height*dpr = k * natural, same k). One zoomed screenshot -> screenshots/crisp/.
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const out = 'screenshots/crisp'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
const errors = []

for (const dpr of [1, 1.25, 1.5]) {
  for (const [width, height] of [[1280, 720], [1920, 1080]]) {
    const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dpr })
    const page = await ctx.newPage()
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(`${base}/fly`)
    await page.getByLabel('preset').selectOption('champion_e1s')
    await page.waitForFunction(() => {
      const rows = [...document.querySelectorAll('.sg-row')]
      return rows.length > 0 && rows.every((r) => { const i = r.querySelector('img[data-testid=object-icon]'); return i && i.complete && i.naturalWidth > 0 })
    }, null, { timeout: 300_000 })
    await page.waitForTimeout(300)
    const icons = await page.evaluate(() => [...document.querySelectorAll('.sg-row img[data-testid=object-icon]')].map((i) => {
      const r = i.getBoundingClientRect(), b = i.parentElement.getBoundingClientRect(), d = window.devicePixelRatio
      return { src: i.getAttribute('src'), nw: i.naturalWidth, nh: i.naturalHeight, w: r.width * d, h: r.height * d, boxW: b.width * d, boxH: b.height * d }
    }))
    assert.ok(icons.length > 0)
    for (const i of icons) {
      const kx = i.w / i.nw, ky = i.h / i.nh, k = Math.round(kx)
      assert.ok(k >= 1 && Math.abs(kx - k) < 0.03 && Math.abs(ky - k) < 0.03,
        `${i.src} at dpr ${dpr} ${width}x${height}: drawn ${i.w.toFixed(2)}x${i.h.toFixed(2)} device px for natural ${i.nw}x${i.nh}`)
      assert.ok(i.w <= i.boxW + 0.5 && i.h <= i.boxH + 0.5, `${i.src} fits its box`)
      assert.ok(i.w + i.nw > i.boxW - 0.5 || i.h + i.nh > i.boxH - 0.5, `${i.src}: k=${k} is the largest that fits`)
    }
    console.log(`dpr ${dpr} ${width}x${height}: ${icons.length} icons whole-factor`, icons.map((i) => Math.round(i.w / i.nw)).join(','))
    if (dpr === 1.25 && width === 1280) {
      const grid = page.locator('.sense-grid')
      await grid.scrollIntoViewIfNeeded()
      await grid.screenshot({ path: `${out}/fly_grid_dpr1.25_1280x720.png` })
    }
    await ctx.close()
  }
}
assert.deepEqual(errors, [], 'no page errors')
await browser.close()
console.log('crisp e2e OK')
