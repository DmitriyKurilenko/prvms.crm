import { api } from './http'

/* ---------- Types ---------- */
export interface Trunk {
  id: number
  name: string
  trunk_type: string
  status: string
  status_detail: string
  is_active: boolean
}

export interface Extension {
  id: number
  manager_id: number
  extension: string
  webrtc_enabled: boolean
  voicemail_enabled: boolean
  is_active: boolean
}

export interface IvrMenu {
  id: number
  name: string
  options: Array<Record<string, unknown>>
  timeout: number
  is_active: boolean
}

export interface CallQueue {
  id: number
  name: string
  strategy: string
  members: number[]
  ring_timeout: number
  max_wait_time: number
  announce_position: boolean
  is_active: boolean
}

export interface CallRecord {
  id: number
  uuid: string
  direction: string
  caller_number: string
  called_number: string
  result: string
  duration: number
  manager_id: number | null
  manager_name: string | null
  started_at: string
  record_file: string | null
}

export interface CallFilters {
  result?: string
  direction?: string
  date_from?: string
  date_to?: string
}

export interface WebRTCCredentials {
  wss_url: string
  esl_host: string
  extension: string | null
  sip_password: string | null
  manager_id: number | null
  sip_domain?: string | null
}

/* ---------- Trunks ---------- */
export const listTrunks = () => api<Trunk[]>('/telephony/trunks/')
export const createTrunk = (data: Record<string, unknown>) => api<{ id: number }>('/telephony/trunks/', { method: 'POST', body: data })
export const patchTrunk = (id: number, data: Record<string, unknown>) => api(`/telephony/trunks/${id}/`, { method: 'PATCH', body: data })
export const deleteTrunk = (id: number) => api(`/telephony/trunks/${id}/`, { method: 'DELETE' })
export const testTrunk = (id: number) => api(`/telephony/trunks/${id}/test/`, { method: 'POST' })

/* ---------- Extensions ---------- */
export const listExtensions = () => api<Extension[]>('/telephony/extensions/')
export const createExtension = (data: Record<string, unknown>) => api<{ id: number }>('/telephony/extensions/', { method: 'POST', body: data })
export const patchExtension = (id: number, data: Record<string, unknown>) => api(`/telephony/extensions/${id}/`, { method: 'PATCH', body: data })
export const deleteExtension = (id: number) => api(`/telephony/extensions/${id}/`, { method: 'DELETE' })

/* ---------- IVR ---------- */
export const listIvr = () => api<IvrMenu[]>('/telephony/ivr/')
export const createIvr = (data: Record<string, unknown>) => api<{ id: number }>('/telephony/ivr/', { method: 'POST', body: data })
export const patchIvr = (id: number, data: Record<string, unknown>) => api(`/telephony/ivr/${id}/`, { method: 'PATCH', body: data })
export const deleteIvr = (id: number) => api(`/telephony/ivr/${id}/`, { method: 'DELETE' })

/* ---------- Queues ---------- */
export const listQueues = () => api<CallQueue[]>('/telephony/queues/')
export const createQueue = (data: Record<string, unknown>) => api<{ id: number }>('/telephony/queues/', { method: 'POST', body: data })
export const patchQueue = (id: number, data: Record<string, unknown>) => api(`/telephony/queues/${id}/`, { method: 'PATCH', body: data })
export const deleteQueue = (id: number) => api(`/telephony/queues/${id}/`, { method: 'DELETE' })

/* ---------- Calls ---------- */
export const listCalls = (filters: CallFilters = {}) => {
  const params = new URLSearchParams()
  if (filters.result) params.set('result', filters.result)
  if (filters.direction) params.set('direction', filters.direction)
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  const qs = params.toString()
  return api<CallRecord[]>(`/telephony/calls/${qs ? '?' + qs : ''}`)
}
export const getCall = (id: number) => api<CallRecord>(`/telephony/calls/${id}/`)
export const callStats = () => api<{ total: number; missed: number; avg_duration: number }>('/telephony/stats/')

/* ---------- Originate ---------- */
export const originate = (data: { from_number: string; to_number: string; trunk_id?: number }) =>
  api<{ detail: string; call_id: number; uuid: string }>('/telephony/call/originate', { method: 'POST', body: data })

/* ---------- WebRTC ---------- */
export const getWebRTCCredentials = () => api<WebRTCCredentials>('/telephony/webrtc/credentials')
