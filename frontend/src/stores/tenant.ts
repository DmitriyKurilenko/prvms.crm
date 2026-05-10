import { defineStore } from 'pinia'
import {
  deleteTenantLogo,
  getPlan,
  getPlans,
  getTenant,
  updateTenantSettings,
  uploadTenantLogo
} from '@/api/tenant'
import { setTenantLanguage, setTenantSlug } from '@/api/http'
import type { FeatureCode, PlanCatalogItem, TenantInfo, TenantPlan } from '@/types'

interface TenantState {
  current: TenantInfo | null
  plan: TenantPlan | null
  availablePlans: PlanCatalogItem[]
  loaded: boolean
}

export const useTenantStore = defineStore('tenant', {
  state: (): TenantState => ({
    current: null,
    plan: null,
    availablePlans: [],
    loaded: false
  }),
  getters: {
    hasFeature: (state) => (feature: FeatureCode): boolean => {
      if (!state.plan || !state.plan.features) return false
      return state.plan.features.includes(feature)
    },
    planLoaded: (state) => Boolean(state.plan),
    limitReached: (state) => (field: keyof TenantPlan['usage']) => {
      if (!state.plan) return false
      const limitField = field as 'max_managers' | 'max_contracts_per_month' | 'max_crm_connections' | 'max_pipelines'
      const map: Record<string, keyof TenantPlan> = {
        managers: 'max_managers',
        contracts: 'max_contracts_per_month',
        crm_connections: 'max_crm_connections',
        pipelines: 'max_pipelines'
      }
      const target = map[field] || limitField
      const limit = state.plan[target] as number | null
      const usage = state.plan.usage[field] || 0
      return limit !== null && usage >= limit
    }
  },
  actions: {
    async ensureLoaded() {
      if (this.loaded) return
      await Promise.all([this.reloadTenant(), this.reloadPlan()])
      this.loaded = true
    },

    async reloadTenant() {
      this.current = await getTenant()
      setTenantSlug(this.current.slug)
      setTenantLanguage(this.current.language)
      applyBrandColor(this.current.brand_color)
    },

    async reloadPlan() {
      this.plan = await getPlan()
    },

    async loadAvailablePlans() {
      this.availablePlans = await getPlans()
    },

    async saveSettings(payload: Record<string, unknown>) {
      this.current = await updateTenantSettings(payload)
      setTenantSlug(this.current.slug)
      setTenantLanguage(this.current.language)
      applyBrandColor(this.current.brand_color)
    },

    async uploadLogo(file: File) {
      const result = await uploadTenantLogo(file)
      if (this.current) {
        this.current = { ...this.current, logo_url: result.logo_url }
      }
    },

    async removeLogo() {
      const result = await deleteTenantLogo()
      if (this.current) {
        this.current = { ...this.current, logo_url: result.logo_url }
      }
    }
  }
})

export function applyBrandColor(color?: string | null): void {
  if (typeof document === 'undefined') return
  const value = (color || '').trim()
  if (!value) return
  document.documentElement.style.setProperty('--brand', value)
}
