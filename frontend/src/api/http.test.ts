import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, getTenantSlug, setAccessToken, setTenantSlug } from './http'

describe('api http client', () => {
  beforeEach(() => {
    setAccessToken(null)
    setTenantSlug(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('adds authorization and tenant headers to requests', async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    })
    vi.stubGlobal('fetch', fetchMock as unknown as typeof fetch)

    setAccessToken('token-123')
    setTenantSlug('qa')

    await api('/healthz', { baseURL: 'http://example.local' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [input, init] = fetchMock.mock.calls[0] as [Request | string, RequestInit | undefined]
    const headers =
      init?.headers !== undefined
        ? new Headers(init.headers)
        : input instanceof Request
          ? input.headers
          : new Headers()

    expect(headers.get('Authorization')).toBe('Bearer token-123')
    expect(headers.get('X-Tenant-Slug')).toBe('qa')
  })

  it('keeps tenant slug in memory for current runtime', () => {
    setTenantSlug('demo')
    expect(getTenantSlug()).toBe('demo')
  })
})
