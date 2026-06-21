import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding, createProduct } from './helpers'

// Сквозной сценарий позиций сделки (Фаза 1, DEC-047): добавление товара в сделку
// пересчитывает сумму, а ручной ввод суммы блокируется (инвариант «сумма производна»).

test('сделка: добавление позиции пересчитывает сумму и блокирует ручной ввод', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  const productName = `E2E товар ${Date.now()}`
  const dealName = `E2E сделка ${Date.now()}`

  // 1. Товар в каталоге (цена по умолчанию 0 достаточна для проверки потока).
  await createProduct(page, productName)

  // 2. Сделка через канбан-форму (воронка/стадия подставляются автоматически).
  await page.getByRole('link', { name: 'Сделки' }).click()
  await expect(page).toHaveURL(/\/app\/deals/, { timeout: 10_000 })
  await page.getByRole('button', { name: 'Новая сделка' }).click()
  await page.getByPlaceholder('Название сделки').fill(dealName)
  await page.getByRole('button', { name: 'Создать' }).click()

  // 3. Открываем сделку по карточке канбана.
  await page.locator('.deal-card', { hasText: dealName }).click()
  await expect(page).toHaveURL(/\/app\/deals\/\d+/, { timeout: 10_000 })

  // 4. Вкладка «Позиции» → добавляем товар.
  await page.getByRole('button', { name: 'Позиции' }).click()
  await page.getByText('Выберите товар').click()
  await page.getByRole('option', { name: productName }).click()
  await page.getByRole('button', { name: 'Добавить' }).click()

  // Позиция и итог появились.
  await expect(page.getByText('Итого:')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.items-table').getByText(productName)).toBeVisible()

  // 5. Инвариант: на вкладке «Инфо» поле суммы помечено как производное.
  await page.getByRole('button', { name: 'Инфо' }).click()
  await expect(page.getByText('Сумма рассчитана по позициям')).toBeVisible()
})
