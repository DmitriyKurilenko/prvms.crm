import { api } from './http'
import type { PlanCatalogItem, TenantInfo, TenantPlan } from '@/types'

export type { TenantInfo }

export interface TenantSettings {
  name?: string
  brand_color?: string
  timezone?: string
  language?: string
}

export async function getTenant(): Promise<TenantInfo> {
  return api<TenantInfo>('/tenant/')
}

export async function updateTenantSettings(payload: TenantSettings): Promise<TenantInfo> {
  return api<TenantInfo>('/tenant/settings', {
    method: 'PATCH',
    body: payload
  })
}

export async function uploadTenantLogo(file: File): Promise<{ logo_url: string | null }> {
  const form = new FormData()
  form.append('file', file)
  return api<{ logo_url: string | null }>('/tenant/logo', {
    method: 'POST',
    body: form
  })
}

export async function deleteTenantLogo(): Promise<{ logo_url: string | null }> {
  return api<{ logo_url: string | null }>('/tenant/logo', {
    method: 'DELETE'
  })
}

export async function getPlan(): Promise<TenantPlan> {
  return api<TenantPlan>('/tenant/plan/')
}

export async function getPlans(): Promise<PlanCatalogItem[]> {
  return api<PlanCatalogItem[]>('/tenant/plans/')
}

export interface CheckoutResponse {
  payment_id: number
  amount: number
  status: string
  confirmation_url: string
}

export async function checkout(planSlug: string, months: number = 1): Promise<CheckoutResponse> {
  return api<CheckoutResponse>('/billing/checkout/', {
    method: 'POST',
    body: { plan_slug: planSlug, months }
  })
}

export async function changePlan(planSlug: string) {
  return api('/billing/change-plan/', {
    method: 'POST',
    body: { plan_slug: planSlug }
  })
}

export async function getPayments() {
  return api<Array<Record<string, unknown>>>('/billing/payments/')
}
