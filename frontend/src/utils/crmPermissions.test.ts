import { describe, expect, it } from 'vitest'

import { canViewAnyCrmEntity, normalizeCrmPermissions, normalizeEntityPermission } from './crmPermissions'

describe('crmPermissions utils', () => {
  it('normalizes invalid payload to safe defaults', () => {
    const normalized = normalizeCrmPermissions({})
    expect(normalized.deals.can_view).toBe(false)
    expect(normalized.contacts.can_create).toBe(false)
    expect(normalized.companies.scope).toBe('all')
  })

  it('forces can_view=true when write permissions are enabled', () => {
    const normalized = normalizeEntityPermission({ can_view: false, can_update: true, scope: 'own' })
    expect(normalized.can_view).toBe(true)
    expect(normalized.can_update).toBe(true)
    expect(normalized.scope).toBe('own')
  })

  it('detects at least one readable entity', () => {
    const perms = normalizeCrmPermissions({
      deals: { can_view: true },
      contacts: { can_view: false },
      companies: { can_view: false }
    })
    expect(canViewAnyCrmEntity(perms)).toBe(true)
  })
})
