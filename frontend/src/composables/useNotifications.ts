import { storeToRefs } from 'pinia'
import { useNotificationsStore } from '@/stores/notifications'

export function useNotifications() {
  const notifications = useNotificationsStore()
  const { items, unreadCount, connected } = storeToRefs(notifications)

  return {
    notifications,
    items,
    unreadCount,
    connected,
    connect: () => notifications.connect(),
    load: () => notifications.load(),
    read: (id: number) => notifications.read(id),
    readAll: () => notifications.readAll()
  }
}
