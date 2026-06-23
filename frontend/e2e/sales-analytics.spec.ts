import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий Фазы 10 (планы продаж + аналитика воронки): живой рендер
// новых отчётов и страницы планов через реальные endpoint-ы.

test('аналитика и планы продаж: разделы отображаются', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  await page.getByRole('link', { name: 'Аналитика' }).click()
  await expect(page).toHaveURL(/\/app\/stats/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Аналитика CRM' })).toBeVisible()
  // секции, наполняемые новыми endpoint-ами funnel/forecast
  await expect(page.getByText('Воронка и конверсия')).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText('Прогноз закрытия')).toBeVisible()

  await page.getByRole('link', { name: 'Планы продаж' }).click()
  await expect(page).toHaveURL(/\/app\/sales-targets/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Планы продаж' })).toBeVisible()
  await expect(page.getByText(/Выполнение за/)).toBeVisible({ timeout: 10_000 })
})
