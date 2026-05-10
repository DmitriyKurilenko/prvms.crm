import { ofetch } from 'ofetch'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'

let accessToken: string | null = null
let tenantSlug: string | null = null
let tenantLanguage: string | null = null
let refreshPromise: Promise<string | null> | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

function readTenantSlugFromStorage(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem('tenant_slug')
}

function writeTenantSlugToStorage(slug: string | null): void {
  if (typeof window === 'undefined') return
  if (slug) {
    window.localStorage.setItem('tenant_slug', slug)
  } else {
    window.localStorage.removeItem('tenant_slug')
  }
}

export function setTenantSlug(slug: string | null): void {
  tenantSlug = slug ? slug.trim().toLowerCase() : null
  writeTenantSlugToStorage(tenantSlug)
}

export function getTenantSlug(): string | null {
  if (!tenantSlug) {
    tenantSlug = readTenantSlugFromStorage()
  }
  return tenantSlug
}

export function setTenantLanguage(language: string | null): void {
  tenantLanguage = language ? language.trim().toLowerCase() : null
}

export function getTenantLanguage(): string | null {
  return tenantLanguage
}

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = ofetch<{ access_token: string }>('/auth/refresh', {
      baseURL: API_URL,
      method: 'POST',
      credentials: 'include'
    })
      .then((response) => {
        setAccessToken(response.access_token)
        return response.access_token
      })
      .catch(() => {
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export const api = ofetch.create({
  baseURL: API_URL,
  credentials: 'include',
  retry: 0,
  async onRequest({ options }) {
    const headers = new Headers(options.headers || {})
    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`)
    }
    const slug = getTenantSlug()
    if (slug) {
      headers.set('X-Tenant-Slug', slug)
    }
    const language = getTenantLanguage()
    if (language && !headers.has('Accept-Language')) {
      headers.set('Accept-Language', language)
    }
    options.headers = headers
  },
  async onResponseError(ctx) {
    const status = ctx.response?.status || 0
    const request = String(ctx.request)
    const isAuthEndpoint = request.includes('/auth/login') || request.includes('/auth/register') || request.includes('/auth/refresh')

    if (status !== 401 || isAuthEndpoint) {
      throw ctx.error
    }

    const newToken = await refreshAccessToken()
    if (!newToken) {
      throw ctx.error
    }

    const headers = new Headers(ctx.options.headers || {})
    headers.set('Authorization', `Bearer ${newToken}`)

    return ofetch(ctx.request, {
      ...ctx.options,
      headers,
      baseURL: API_URL,
      credentials: 'include'
    })
  }
})
