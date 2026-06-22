import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий Фазы 9 (календарь, напоминания, повторяемость): создание
// задачи из календаря и её появление в сетке месяца.

test('календарь: создание задачи отображается в сетке', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  await page.getByRole('link', { name: 'Календарь' }).click()
  await expect(page).toHaveURL(/\/app\/calendar/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Календарь' })).toBeVisible()
  // FullCalendar отрисован
  await expect(page.locator('.fc')).toBeVisible({ timeout: 10_000 })

  const title = `E2E задача ${Date.now()}`
  await page.getByRole('button', { name: 'Новая задача' }).click()
  await page.getByPlaceholder('Что нужно сделать').fill(title)
  // поле срока предзаполнено сегодняшним днём; повторение и напоминание оставляем по умолчанию
  await page.getByRole('button', { name: 'Создать' }).click()

  await expect(page.locator('.fc').getByText(title)).toBeVisible({ timeout: 10_000 })
})
