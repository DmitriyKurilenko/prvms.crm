import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной smoke товарного каталога (Фаза 1, DEC-047).
// Предусловие данных: сервис `seed` (seed_demo_users --count 1).

test('каталог: создание товара отображается в списке', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  const productName = `E2E товар ${Date.now()}`

  // Навигация внутри SPA (клиентский роутинг), а не page.goto: полная перезагрузка
  // потеряла бы in-memory access-токен и guard увёл бы на /login.
  await page.getByRole('link', { name: 'Товары' }).click()
  await expect(page).toHaveURL(/\/app\/products/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Товары' })).toBeVisible()

  await page.getByRole('button', { name: 'Новый товар' }).click()
  await page.getByPlaceholder('Название').fill(productName)
  await page.getByRole('button', { name: 'Создать' }).click()

  await expect(page.getByText(productName)).toBeVisible({ timeout: 10_000 })
})
