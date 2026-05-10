import { api, setAccessToken, setTenantSlug } from './http'
import type { AuthUser, OrganizationMembership } from '@/types'

export interface LoginPayload {
  email: string
  password: string
}

interface LoginResponse {
  access_token: string
  tenant_slug?: string | null
}

export async function login(payload: LoginPayload): Promise<void> {
  const data = await api<LoginResponse>('/auth/login', {
    method: 'POST',
    body: payload
  })
  setAccessToken(data.access_token)
  if (data.tenant_slug) {
    setTenantSlug(data.tenant_slug)
  }
}

export async function register(payload: Record<string, unknown>): Promise<{ tenant_slug: string }> {
  const data = await api<{ access_token: string; tenant_slug: string }>('/auth/register', {
    method: 'POST',
    body: payload
  })
  setAccessToken(data.access_token)
  setTenantSlug(data.tenant_slug)
  return { tenant_slug: data.tenant_slug }
}

export async function refresh(): Promise<string | null> {
  try {
    const data = await api<{ access_token: string; tenant_slug?: string | null }>('/auth/refresh', {
      method: 'POST'
    })
    setAccessToken(data.access_token)
    if (data.tenant_slug) {
      setTenantSlug(data.tenant_slug)
    }
    return data.access_token
  } catch {
    return null
  }
}

export async function me(): Promise<AuthUser> {
  return api<AuthUser>('/auth/me')
}

export async function logout(): Promise<void> {
  await api('/auth/logout', { method: 'POST' })
  setAccessToken(null)
  setTenantSlug(null)
}

export interface InviteInfo {
  email: string
  org_name: string
  role: string
  has_account: boolean
}

export async function checkInvite(token: string): Promise<InviteInfo> {
  return api<InviteInfo>('/auth/invite/check', {
    params: { token }
  })
}

export async function acceptInvite(payload: { token: string; password?: string; username?: string }): Promise<void> {
  const data = await api<{ access_token: string; tenant_slug?: string | null }>('/auth/invite/accept', {
    method: 'POST',
    body: payload
  })
  setAccessToken(data.access_token)
  if (data.tenant_slug) {
    setTenantSlug(data.tenant_slug)
  }
}

export async function listOrganizations(): Promise<OrganizationMembership[]> {
  return api<OrganizationMembership[]>('/auth/organizations')
}

export async function switchTenant(tenantSlug: string): Promise<void> {
  const data = await api<{ access_token: string; tenant_slug?: string | null }>('/auth/switch-tenant', {
    method: 'POST',
    body: { tenant_slug: tenantSlug }
  })
  setAccessToken(data.access_token)
  if (data.tenant_slug) {
    setTenantSlug(data.tenant_slug)
  }
}
