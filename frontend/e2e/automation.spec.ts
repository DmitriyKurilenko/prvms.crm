import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий автоматизаций (Фаза 5, DEC-052): создание правила
// «если создана сделка → создать задачу» и появление его в списке.

test('автоматизации: создание правила отображается в списке', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  const ruleName = `E2E правило ${Date.now()}`

  await page.getByRole('link', { name: 'Автоматизации' }).click()
  await expect(page).toHaveURL(/\/app\/automation/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Автоматизации' })).toBeVisible()

  await page.getByRole('button', { name: 'Новое правило' }).click()
  await page.getByPlaceholder('Название правила').fill(ruleName)
  // Триггер «Создана сделка» и действие «Создать задачу» — значения по умолчанию.
  await page.getByPlaceholder('Например, «Перезвонить клиенту»').fill('Связаться с клиентом')
  await page.getByRole('button', { name: 'Создать', exact: true }).click()

  await expect(page.getByRole('cell', { name: ruleName })).toBeVisible({ timeout: 10_000 })
})
