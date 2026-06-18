import { api } from './http'

/* ---------- Types ---------- */
export interface ExolveChannelInfo {
  exolve_number: string
  number_code: string
  status: string
  status_detail: string
  is_active: boolean
}

export interface SipAccount {
  id: number
  manager_id: number
  manager_name: string
  username: string
  display_number: string
  status: string
  status_detail: string
  is_active: boolean
}

export interface WebRTCCredentials {
  sip_domain: string
  wss_url: string | null
  username: string | null
  password: string | null
  display_number: string | null
  manager_id: number | null
  ready: boolean
}

export interface CallRecord {
  id: number
  call_sid: string
  direction: string
  caller_number: string
  called_number: string
  result: string
  duration: number
  talk_time: number
  manager_id: number | null
  manager_name: string | null
  crm_contact_id: string
  crm_lead_id: string
  started_at: string
  record_file: string | null
}

export interface CallFilters {
  result?: string
  direction?: string
  date_from?: string
  date_to?: string
}

/* ---------- Channel & number provisioning ---------- */
export const getChannel = () => api<ExolveChannelInfo>('/telephony/channel/')
export const getNumberReference = () => api<Record<string, unknown>>('/telephony/number-reference/')
export const getAvailableNumbers = (params: { type_id?: number; region_id?: number; mask?: string; limit?: number } = {}) => {
  const qs = new URLSearchParams()
  if (params.type_id) qs.set('type_id', String(params.type_id))
  if (params.region_id) qs.set('region_id', String(params.region_id))
  if (params.mask) qs.set('mask', params.mask)
  if (params.limit) qs.set('limit', String(params.limit))
  const s = qs.toString()
  return api<Record<string, unknown>>(`/telephony/available-numbers/${s ? '?' + s : ''}`)
}
export const connectNumber = (data: { number_code: string; number: string; type_id?: number; region_id?: number }) =>
  api<{ status: string; exolve_number: string; detail: string }>('/telephony/connect-number/', { method: 'POST', body: data })

/* ---------- SIP accounts ---------- */
export const listSipAccounts = () => api<SipAccount[]>('/telephony/sip-accounts/')
export const provisionSipAccounts = () => api<{ provisioned: number }>('/telephony/sip-accounts/provision/', { method: 'POST' })

/* ---------- WebRTC (Web Voice SDK) ---------- */
export const getWebRTCCredentials = () => api<WebRTCCredentials>('/telephony/webrtc-credentials/')

/* ---------- Click-to-call (журналирование исходящего) ---------- */
export const clickToCall = (data: { to_number: string; deal_id?: number; contact_id?: number }) =>
  api<{ call_id: number; to_number: string }>('/telephony/click-to-call/', { method: 'POST', body: data })

/* ---------- Client diagnostics (softphone → server logs) ---------- */
export const clientLog = (event: string, detail = '') =>
  api('/telephony/client-log/', { method: 'POST', body: { event, detail } }).catch(() => {})

/* ---------- Call journal ---------- */
export const listCalls = (filters: CallFilters = {}) => {
  const qs = new URLSearchParams()
  if (filters.result) qs.set('result', filters.result)
  if (filters.direction) qs.set('direction', filters.direction)
  if (filters.date_from) qs.set('date_from', filters.date_from)
  if (filters.date_to) qs.set('date_to', filters.date_to)
  const s = qs.toString()
  return api<CallRecord[]>(`/telephony/calls/${s ? '?' + s : ''}`)
}
export const callStats = () => api<{ total: number; missed: number; answered: number }>('/telephony/stats/')
