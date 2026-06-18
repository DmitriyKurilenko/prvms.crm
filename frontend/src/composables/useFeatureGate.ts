import { useTenantStore } from '@/stores/tenant'
import type { FeatureCode } from '@/types'

export function useFeatureGate() {
  const tenant = useTenantStore()

  const hasFeature = (code: FeatureCode): boolean => tenant.hasFeature(code)

  const checkLimit = (field: string, current: number): boolean => {
    const plan = tenant.plan
    if (!plan) return true

    const map: Record<string, number | null | undefined> = {
      max_managers: plan.max_managers,
      max_documents_per_month: plan.max_documents_per_month,
      max_crm_connections: plan.max_crm_connections,
      max_pipelines: plan.max_pipelines
    }

    const limit = map[field]
    if (limit === null || limit === undefined) return true
    return current < limit
  }

  return {
    hasFeature,
    checkLimit
  }
}
