import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий тегов (Фаза 7, DEC-051): создание тега и появление в списке.

test('теги: создание тега отображается в списке', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  const tagName = `E2E тег ${Date.now()}`

  await page.getByRole('link', { name: 'Теги' }).click()
  await expect(page).toHaveURL(/\/app\/tags/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Теги' })).toBeVisible()

  await page.getByPlaceholder('Название тега').fill(tagName)
  await page.getByRole('button', { name: 'Добавить' }).click()

  await expect(page.getByText(tagName)).toBeVisible({ timeout: 10_000 })
})
