// Memory / speed over many live runs, real UI against the real backend (python tools/e2e_stack.py e2e/leak.mjs).
// Runs champion_e1s on 1-1 N times in a row (Restart from the run screen, as a user would) at Fast speed. Per run it prints
// one JSON line: the browser's JS heap after a forced GC, and the frames/s of the live stream (frames over the time from the
// first picture to the end banner). RUNS=10 by default.
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const RUNS = Number(process.env.RUNS ?? 10)
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const cdp = await page.context().newCDPSession(page)
await cdp.send('Performance.enable')
let frames = 0
page.on('websocket', (ws) => ws.on('framereceived', ({ payload }) => {
  if (typeof payload === 'string' && payload.startsWith('{"type":"frame"')) frames++
}))
const heapMb = async () => {
  await cdp.send('HeapProfiler.collectGarbage')
  const { metrics } = await cdp.send('Performance.getMetrics')
  return +(metrics.find((m) => m.name === 'JSHeapUsedSize').value / 1048576).toFixed(1)
}

await page.goto(`${base}/scene`)
await page.locator('[data-level="1-1"]').click()
await page.getByRole('button', { name: 'Whole level' }).click()
await page.getByLabel('the level start').check()
await page.getByText('Next: choose the fly').click()
await page.getByLabel('preset').selectOption('champion_e1s')
await page.getByLabel('Home').waitFor()
await page.getByText('▶ Run', { exact: true }).click()

for (let i = 1; i <= RUNS; i++) {
  await page.locator('[data-testid=picture]').waitFor({ timeout: 120_000 })
  frames = 0
  const t0 = Date.now()
  await page.getByRole('button', { name: 'Fast' }).click()
  await page.locator('.banner[role=status]').waitFor({ timeout: 600_000 })
  const secs = (Date.now() - t0) / 1000
  await page.waitForTimeout(500)
  console.log(JSON.stringify({ run: i, heap_mb: await heapMb(), frames, secs: +secs.toFixed(1), fps: +(frames / secs).toFixed(1) }))
  if (i < RUNS) {
    await page.locator('button[aria-label=restart]').click()
    await page.locator('.banner[role=status]').waitFor({ state: 'detached' })
  }
}
await browser.close()
