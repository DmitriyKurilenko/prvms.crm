import { defineStore } from 'pinia'
import {
  listOrganizations as listOrganizationsApi,
  login as loginApi,
  logout as logoutApi,
  me,
  refresh,
  register as registerApi,
  switchTenant as switchTenantApi
} from '@/api/auth'
import type { RegisterPayload } from '@/api/auth'
import { getAccessToken, setTenantSlug } from '@/api/http'
import { useTenantStore } from '@/stores/tenant'
import type { AuthUser, OrganizationMembership } from '@/types'

interface AuthState {
  user: AuthUser | null
  organizations: OrganizationMembership[]
  initialized: boolean
  loading: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    organizations: [],
    initialized: false,
    loading: false
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user && getAccessToken()),
    role: (state) => state.user?.role || null
  },
  actions: {
    async initialize() {
      if (this.initialized) return
      this.loading = true
      const token = await refresh()
      if (token) {
        try {
          this.user = await me()
          setTenantSlug(this.user.tenant_slug)
          this.organizations = await listOrganizationsApi()
        } catch {
          // Don't clear token/slug — keep whatever refresh() set.
          // User data will be fetched on next navigation if needed.
        }
      }
      this.initialized = true
      this.loading = false
    },

    async login(email: string, password: string) {
      this.loading = true
      const tenant = useTenantStore()
      tenant.$reset()
      await loginApi({ email, password })
      this.user = await me()
      setTenantSlug(this.user.tenant_slug)
      this.organizations = await listOrganizationsApi()
      this.loading = false
    },

    async register(payload: RegisterPayload) {
      this.loading = true
      const tenant = useTenantStore()
      tenant.$reset()
      await registerApi(payload)
      this.user = await me()
      setTenantSlug(this.user.tenant_slug)
      this.organizations = await listOrganizationsApi()
      this.loading = false
    },

    async refreshOrganizations() {
      this.organizations = await listOrganizationsApi()
    },

    async switchOrganization(tenantSlug: string) {
      const normalized = tenantSlug?.trim().toLowerCase()
      if (!normalized || this.user?.tenant_slug === normalized) return
      this.loading = true
      const tenant = useTenantStore()
      try {
        await switchTenantApi(normalized)
        this.user = await me()
        await Promise.all([tenant.reloadTenant(), tenant.reloadPlan(), this.refreshOrganizations()])
      } finally {
        this.loading = false
      }
    },

    async logout() {
      const tenant = useTenantStore()
      tenant.$reset()
      await logoutApi()
      this.user = null
      this.organizations = []
      setTenantSlug(null)
      this.initialized = true
    }
  }
})
