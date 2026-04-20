import { api } from './http'

export interface UiNotification {
  id: number
  event: string
  title: string
  body: string
  link: string
  is_read: boolean
  channel: string
  sent_at: string
}

export interface NotificationPreference {
  event: string
  channel: string
  is_enabled: boolean
  recipient_roles: string[]
}

export interface TelegramStatus {
  linked: boolean
  chat_id: number | null
  username: string
  bot_username: string
}

export interface TelegramLinkInit {
  detail: string
  bind_token: string
  telegram_link: string
}

export async function listNotifications(): Promise<UiNotification[]> {
  return api<UiNotification[]>('/notifications/')
}

export async function markRead(id: number): Promise<void> {
  await api(`/notifications/${id}/read/`, { method: 'POST' })
}

export async function markAllRead(): Promise<void> {
  await api('/notifications/read-all/', { method: 'POST' })
}

export async function sendTestNotification(): Promise<void> {
  await api('/notifications/test/', { method: 'POST' })
}

export async function listPreferences(): Promise<NotificationPreference[]> {
  return api<NotificationPreference[]>('/notifications/preferences/')
}

export async function updatePreferences(prefs: NotificationPreference[]): Promise<void> {
  await api('/notifications/preferences/', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  })
}

export async function telegramStatus(): Promise<TelegramStatus> {
  return api<TelegramStatus>('/notifications/telegram/status/')
}

export async function linkTelegramInit(): Promise<TelegramLinkInit> {
  return api<TelegramLinkInit>('/notifications/telegram/link/', { method: 'POST' })
}

export async function unlinkTelegram(): Promise<void> {
  await api('/notifications/telegram/unlink/', { method: 'DELETE' })
}
