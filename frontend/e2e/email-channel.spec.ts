import { test, expect } from '@playwright/test'
import { loginAndSkipOnboarding } from './helpers'

// Сквозной сценарий формы email-канала (Фаза 3, DEC-049): создание канала
// «Электронная почта» через Настройки → Мессенджеры и появление его в списке.

test('email-канал: создаётся через форму и появляется в списке', async ({ page }) => {
  await loginAndSkipOnboarding(page)

  const channelName = `E2E почта ${Date.now()}`

  await page.getByRole('link', { name: 'Настройки' }).click()
  await expect(page).toHaveURL(/\/app\/settings/, { timeout: 10_000 })
  await page.getByRole('button', { name: 'Мессенджеры' }).click()

  await expect(page.getByRole('heading', { name: 'Подключить канал' })).toBeVisible({ timeout: 10_000 })
  await page.getByPlaceholder('Мой Telegram бот').fill(channelName)

  // Тип канала → «Электронная почта». Селект стартует со значением «Telegram Bot»
  // (дефолт формы), поэтому открываем сам компонент, а не плейсхолдер.
  await page.locator('.p-select').first().click()
  await page.getByRole('option', { name: 'Электронная почта' }).click()

  // Поля IMAP/SMTP (значения для создания достаточно валидных по форме).
  await page.getByPlaceholder('imap.example.com').fill('imap.example.com')
  await page.getByPlaceholder('smtp.example.com').fill('smtp.example.com')
  await page.getByPlaceholder('sales@example.com').fill('sales@example.com')
  await page.getByPlaceholder('••••••').fill('secret-pass')

  // exact:true — иначе «Подключить» совпадает и с кнопкой «Подключить ВКонтакте».
  await page.getByRole('button', { name: 'Подключить', exact: true }).click()

  // Канал появился в таблице с типом «Электронная почта».
  // Проверяем по ячейкам (тип иначе совпал бы и с комбобоксом формы).
  await expect(page.getByRole('cell', { name: channelName })).toBeVisible({ timeout: 10_000 })
  // .first(): seed-тенант может накапливать email-каналы между прогонами.
  await expect(page.getByRole('cell', { name: 'Электронная почта' }).first()).toBeVisible()
})
