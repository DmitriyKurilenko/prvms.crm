import { describe, it, expect } from 'vitest'
import { formatDate, formatDateTime, formatTime } from './datetime'

// Без активной Pinia resolveLocale() падает в fallback 'ru-RU', а resolveTimeZone()
// возвращает undefined — функции работают изолированно. Ассерты намеренно не
// привязаны к точному часу (зависит от таймзоны среды), а проверяют структуру.

describe('datetime formatters', () => {
  it('возвращают пустую строку для пустого ввода', () => {
    expect(formatDateTime(null)).toBe('')
    expect(formatDateTime(undefined)).toBe('')
    expect(formatDateTime('')).toBe('')
    expect(formatDate(null)).toBe('')
    expect(formatTime(undefined)).toBe('')
  })

  it('возвращают пустую строку для невалидной даты', () => {
    expect(formatDateTime('not-a-date')).toBe('')
    expect(formatDate('сегодня')).toBe('')
  })

  it('formatDateTime форматирует валидную дату с годом и временем', () => {
    const out = formatDateTime('2026-06-15T12:00:00Z')
    expect(out).not.toBe('')
    expect(out).toContain('2026')
    expect(out).toContain(':') // присутствует время
  })

  it('formatDate не содержит времени (часы/минуты убраны)', () => {
    const out = formatDate('2026-06-15T12:00:00Z')
    expect(out).not.toBe('')
    expect(out).toContain('2026')
    expect(out).not.toContain(':')
  })

  it('formatTime содержит время и не содержит года', () => {
    const out = formatTime('2026-06-15T12:00:00Z')
    expect(out).toContain(':')
    expect(out).not.toContain('2026')
  })

  it('принимают объект Date напрямую', () => {
    const out = formatDate(new Date('2026-01-20T09:30:00Z'))
    expect(out).toContain('2026')
  })
})
