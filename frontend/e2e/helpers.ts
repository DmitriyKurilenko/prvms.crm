import { expect, type Page } from '@playwright/test'

// Общие шаги e2e: вход и пропуск онбординга свежего тенанта.
// Предусловие данных обеспечивает сервис `seed` (seed_demo_users --count 1).

export const LOGIN = process.env.E2E_LOGIN || 'test1@test.ru'
export const PASSWORD = process.env.E2E_PASSWORD || 'Asdf2121'

export async function loginAndSkipOnboarding(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('Email или username').fill(LOGIN)
  await page.getByPlaceholder('Пароль').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page).toHaveURL(/\/app/, { timeout: 15_000 })

  // Свежий тенант открывает мастер онбординга. Скип двухшаговый: кнопка «Пропустить»
  // открывает диалог подтверждения со второй кнопкой «Пропустить».
  const skipBtn = page.getByRole('button', { name: 'Пропустить' }).first()
  if (await skipBtn.isVisible().catch(() => false)) {
    await skipBtn.click()
    await expect(page.getByText('Пропустить настройку?')).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: 'Пропустить' }).last().click()
    await expect(page.getByText('Пропустить настройку?')).toBeHidden({ timeout: 10_000 })
  }
}

// Создаёт товар через раздел «Товары» (клиентская навигация по меню) и возвращает имя.
export async function createProduct(page: Page, name: string): Promise<void> {
  await page.getByRole('link', { name: 'Товары' }).click()
  await expect(page).toHaveURL(/\/app\/products/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Товары' })).toBeVisible()
  await page.getByRole('button', { name: 'Новый товар' }).click()
  await page.getByPlaceholder('Название').fill(name)
  await page.getByRole('button', { name: 'Создать' }).click()
  await expect(page.getByText(name)).toBeVisible({ timeout: 10_000 })
}
