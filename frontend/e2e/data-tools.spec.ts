import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий Фазы 6 (импорт/экспорт + дедуп/слияние): навигация,
// живой экспорт CSV (download-событие) и живой запрос дублей через API.

test('импорт/экспорт: экспорт CSV и поиск дублей контактов', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  await page.getByRole('link', { name: 'Импорт/экспорт' }).click()
  await expect(page).toHaveURL(/\/app\/data-tools/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Импорт и экспорт' })).toBeVisible()

  // Экспорт: вкладка → скачивание реального CSV-файла.
  await page.getByRole('button', { name: 'Экспорт' }).click()
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Скачать CSV' }).click(),
  ])
  expect(download.suggestedFilename()).toBe('contacts.csv')

  // Дубли: вкладка → живой запрос к /crm/duplicates/contacts/.
  await page.getByRole('button', { name: 'Дубли' }).click()
  await page.getByRole('button', { name: 'Найти дубли' }).click()
  await expect(page.getByText(/Дублей не найдено|Совпадение по/)).toBeVisible({ timeout: 10_000 })
})
