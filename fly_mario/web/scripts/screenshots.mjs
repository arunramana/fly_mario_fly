// Usage: npm run dev (port 5173), then `node scripts/screenshots.mjs`
import { chromium } from 'playwright'

const base = process.env.BASE ?? 'http://localhost:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const shot = (n) => page.screenshot({ path: `screenshots/${n}.png`, fullPage: true })

await page.goto(`${base}/scene`)
await page.getByText('Goomba only').waitFor()
await page.getByText('Goomba only').click()
await shot('1-scene')

await page.getByText('Next ▶').click()
await page.getByLabel('preset').selectOption('cautious')
await page.getByLabel('Sour on Pit').click()
await page.getByText('Advanced').click()
await page.waitForTimeout(400)
await shot('2-fly')

await page.getByText('Run ▶').click()
await page.getByText('Save this moment').waitFor()
await page.waitForTimeout(1500)
await page.getByText('Save this moment').click()
await page.getByText('THE FLY DIED').waitFor({ timeout: 15000 })
await shot('3-run')

await page.getByText('Rewind 3 s').click()
await page.getByText('Resume from here').waitFor()
await page.waitForTimeout(400)
await shot('4-moment')

await browser.close()
