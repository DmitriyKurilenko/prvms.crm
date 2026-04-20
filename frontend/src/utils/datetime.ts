import { useTenantStore } from '@/stores/tenant'

export type DateInput = string | number | Date | null | undefined

const LOCALE_MAP: Record<string, string> = {
  ru: 'ru-RU',
  en: 'en-US'
}

function resolveLocale(): string {
  try {
    const store = useTenantStore()
    const language = store.current?.language
    if (language && LOCALE_MAP[language]) return LOCALE_MAP[language]
  } catch {
    // Pinia store may not be active (SSR / tests) — fall through
  }
  return 'ru-RU'
}

function resolveTimeZone(): string | undefined {
  try {
    const store = useTenantStore()
    return store.current?.timezone || undefined
  } catch {
    return undefined
  }
}

function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) return value
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTime(value: DateInput, options?: Intl.DateTimeFormatOptions): string {
  const date = toDate(value)
  if (!date) return ''
  const opts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: resolveTimeZone(),
    ...options
  }
  return new Intl.DateTimeFormat(resolveLocale(), opts).format(date)
}

export function formatDate(value: DateInput, options?: Intl.DateTimeFormatOptions): string {
  return formatDateTime(value, { hour: undefined, minute: undefined, ...options })
}

export function formatTime(value: DateInput, options?: Intl.DateTimeFormatOptions): string {
  return formatDateTime(value, {
    year: undefined,
    month: undefined,
    day: undefined,
    hour: '2-digit',
    minute: '2-digit',
    ...options
  })
}
