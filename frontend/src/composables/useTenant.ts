import { storeToRefs } from 'pinia'
import { useTenantStore } from '@/stores/tenant'

export function useTenant() {
  const tenant = useTenantStore()
  const { current, plan, availablePlans } = storeToRefs(tenant)

  return {
    tenant,
    current,
    plan,
    availablePlans,
    load: () => tenant.ensureLoaded(),
    reloadPlan: () => tenant.reloadPlan()
  }
}
