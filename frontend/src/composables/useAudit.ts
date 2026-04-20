import { api } from '@/api/http'

export function useAudit() {
  const loadEvents = async () => api('/audit/events/')
  const loadEvent = async (id: number) => api(`/audit/events/${id}/`)

  return {
    loadEvents,
    loadEvent
  }
}
