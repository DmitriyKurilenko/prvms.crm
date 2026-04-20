import { api } from '@/api/http'
import type {
  IntegrationConnection,
  IntegrationErrorLogEntry,
  IntegrationMode,
  IntegrationType,
  OAuthStartResponse
} from '@/types'

interface ConnectionPayload {
  crm_type: IntegrationType
  name: string
  credentials: Record<string, unknown>
  integration_mode?: IntegrationMode
}

interface UpdateConnectionPayload {
  name?: string
  credentials?: Record<string, unknown>
  is_active?: boolean
  integration_mode?: IntegrationMode
}

interface OAuthStartPayload {
  connection_id?: number
  name?: string
  redirect_uri?: string
  install_mode?: 'oauth' | 'marketplace'
}

export async function listConnections() {
  return api<IntegrationConnection[]>('/integrations/connections/')
}

export async function createConnection(payload: ConnectionPayload) {
  return api<{ id: number; status_code: string; status_label: string; missing_scopes: string[] }>('/integrations/connections/', {
    method: 'POST',
    body: payload
  })
}

export async function updateConnection(connectionId: number, payload: UpdateConnectionPayload) {
  return api(`/integrations/connections/${connectionId}/`, {
    method: 'PATCH',
    body: payload
  })
}

export async function deleteConnection(connectionId: number) {
  return api(`/integrations/connections/${connectionId}/`, { method: 'DELETE' })
}

export async function syncConnectionUsers(connectionId: number) {
  return api(`/integrations/connections/${connectionId}/sync-users/`, { method: 'POST' })
}

export async function healthCheckConnection(connectionId: number) {
  return api(`/integrations/connections/${connectionId}/health-check/`, { method: 'POST' })
}

export async function testConnection(connectionId: number) {
  return api<{
    connection: { ok: boolean; detail: string }
    webhook: { ok: boolean; detail: string; webhook_url: string | null; last_received_at: string | null }
    status_code: string
    status_label: string
    status_detail: string
  }>(`/integrations/connections/${connectionId}/test/`, { method: 'POST' })
}

export async function reconnectConnection(connectionId: number) {
  return api(`/integrations/connections/${connectionId}/reconnect/`, { method: 'POST' })
}

export async function listConnectionErrors(connectionId: number) {
  return api<IntegrationErrorLogEntry[]>(`/integrations/connections/${connectionId}/errors/`)
}

export async function startOAuth(crmType: IntegrationType, payload: OAuthStartPayload) {
  return api<OAuthStartResponse>(`/integrations/oauth/${crmType}/start/`, {
    method: 'POST',
    body: payload
  })
}

export async function startMarketplaceInstall(crmType: IntegrationType, payload: OAuthStartPayload) {
  return api<OAuthStartResponse>(`/integrations/marketplace/${crmType}/install/`, {
    method: 'POST',
    body: payload
  })
}
