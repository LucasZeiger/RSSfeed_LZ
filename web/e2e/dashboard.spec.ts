import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
const demo = JSON.parse(readFileSync(new URL('../public/data/demo.json', import.meta.url), 'utf8'))

test('demo briefing, evidence, metrics and dialog keyboard access', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/?data=demo')
  await expect(page.locator('.story-card')).toHaveCount(6)
  await expect(page.locator('.demo-banner')).toContainText('fictional')
  await page.locator('.story-link').first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByRole('heading', { name: 'Possible economic consequences' }),
  ).toBeVisible()
  await expect(dialog.locator('.perspective a')).toHaveCount(3)
  await expect(dialog).toContainText('does not establish that the event caused it')
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  expect(errors).toEqual([])
})

test('region, search, insufficient coverage and persisted preference', async ({ page }) => {
  await page.goto('/?data=demo')
  await page.getByLabel('Region', { exact: true }).selectOption('AT')
  await expect(page.locator('.story-card')).toHaveCount(1)
  await expect(page.locator('.story-card')).toContainText('Österreich')
  await page.reload()
  await expect(page.getByLabel('Region', { exact: true })).toHaveValue('AT')
  await page.locator('.story-link').first().click()
  await expect(page.getByRole('dialog')).toContainText('Insufficient coverage for comparison.')
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await page.getByLabel('Search stories').fill('NVDA')
  await expect(page.locator('.story-card')).toHaveCount(1)
  await page.getByLabel('Search stories').fill('no-such-story')
  await expect(page.getByRole('heading', { name: 'No stories match these filters' })).toBeVisible()
})

test('live mode never falls back to fabricated data', async ({ page }) => {
  await page.route('**/data/latest.json', (route) =>
    route.fulfill({ status: 404, body: 'Not found' }),
  )
  await page.goto('/?data=live')
  await expect(page.getByRole('alert')).toContainText('No real dataset has been published')
  await expect(page.locator('.demo-banner')).toHaveCount(0)
  await expect(page.locator('.story-card')).toHaveCount(0)
})

test('failed refresh retains last valid dataset and surfaces pipeline status', async ({ page }) => {
  // Synthetic data is used only as a mocked network response inside this test.
  let failRefresh = false
  await page.route('**/data/latest.json', (route) => {
    return !failRefresh
      ? route.fulfill({ json: { ...demo, mode: 'live', status: { ...demo.status, state: 'ok' } } })
      : route.fulfill({ status: 503 })
  })
  await page.route('**/data/status.json', (route) =>
    route.fulfill({ json: { ...demo.status, state: 'failed', errors: ['bbc-world: offline'] } }),
  )
  await page.goto('/?data=live')
  await expect(page.locator('.run-status')).toContainText('failed')
  await expect(page.locator('.story-card')).toHaveCount(6)
  failRefresh = true
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('.story-card')).toHaveCount(6)
})

test('mobile layout has no overflow and navigation works', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?data=demo')
  await expect(page.locator('.story-card')).toHaveCount(6)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Toggle navigation' }).click()
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: 'Markets', exact: true })
    .click()
  await expect(page.locator('.market-tile')).toHaveCount(8)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('desktop visual checkpoint', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.goto('/?data=demo')
  await expect(page.locator('.story-card')).toHaveCount(6)
  await page.screenshot({ path: '/tmp/newslens-desktop.png', fullPage: true })
})
