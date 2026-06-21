import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий конструктора веб-форм (Фаза 4, DEC-050): создание формы
// в ЛК и получение кода для вставки.

test('веб-формы: создание формы и показ кода для вставки', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  const formName = `E2E форма ${Date.now()}`

  await page.getByRole('link', { name: 'Веб-формы' }).click()
  await expect(page).toHaveURL(/\/app\/webforms/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Веб-формы' })).toBeVisible()

  await page.getByRole('button', { name: 'Новая форма' }).click()
  await page.getByPlaceholder('Название формы').fill(formName)
  // Воронка и первая стадия подставляются автоматически (дефолтная воронка тенанта).
  await page.getByRole('button', { name: 'Создать', exact: true }).click()

  // После создания открывается диалог с кодом для вставки (заголовок PDialog не
  // является heading, поэтому проверяем по тексту сниппета).
  await expect(page.getByText('/widget/crm-webform.js')).toBeVisible({ timeout: 10_000 })

  // Закрываем диалог и убеждаемся, что форма в списке.
  await page.keyboard.press('Escape')
  await expect(page.getByRole('cell', { name: formName })).toBeVisible({ timeout: 10_000 })
})
