import type { CrmEntityPermission, CrmPermissionMap, CrmPermissionScope } from '@/types'

const DEFAULT_SCOPE: CrmPermissionScope = 'all'

export const emptyEntityPermission: CrmEntityPermission = {
  can_view: false,
  can_create: false,
  can_update: false,
  can_delete: false,
  scope: DEFAULT_SCOPE
}

const VALID_SCOPES = new Set<CrmPermissionScope>(['all', 'team', 'own'])

export function normalizeEntityPermission(input: unknown): CrmEntityPermission {
  const raw = (input ?? {}) as Partial<CrmEntityPermission>
  const scopeRaw = String(raw.scope || DEFAULT_SCOPE).toLowerCase() as CrmPermissionScope

  const normalized: CrmEntityPermission = {
    can_view: Boolean(raw.can_view),
    can_create: Boolean(raw.can_create),
    can_update: Boolean(raw.can_update),
    can_delete: Boolean(raw.can_delete),
    scope: VALID_SCOPES.has(scopeRaw) ? scopeRaw : DEFAULT_SCOPE
  }

  if (normalized.can_create || normalized.can_update || normalized.can_delete) {
    normalized.can_view = true
  }
  if (!normalized.can_view) {
    normalized.can_create = false
    normalized.can_update = false
    normalized.can_delete = false
  }

  return normalized
}

export function normalizeCrmPermissions(input: unknown): CrmPermissionMap {
  const raw = (input ?? {}) as Record<string, unknown>
  return {
    deals: normalizeEntityPermission(raw.deals),
    contacts: normalizeEntityPermission(raw.contacts),
    companies: normalizeEntityPermission(raw.companies),
    products: normalizeEntityPermission(raw.products),
    webforms: normalizeEntityPermission(raw.webforms)
  }
}

export function canViewAnyCrmEntity(perms: CrmPermissionMap): boolean {
  return perms.deals.can_view || perms.contacts.can_view || perms.companies.can_view
}
