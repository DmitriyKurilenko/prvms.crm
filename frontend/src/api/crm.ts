import { api } from './http'

/* ---------- Types ---------- */
export interface CrmContact {
  id: number
  first_name: string
  last_name: string
  phone: string
  email: string
  company_id: number | null
  responsible_id: number | null
  created_at: string
}

export interface CrmCompany {
  id: number
  name: string
  inn: string
  phone: string
  email: string
  contacts_count?: number
  deals_count?: number
  created_at: string
}

export interface CrmPipeline {
  id: number
  name: string
  is_default: boolean
  sort_order: number
  is_active: boolean
}

export interface CrmStage {
  id: number
  name: string
  stage_type: string
  color: string
  sort_order: number
  auto_action: Record<string, unknown>
}

export interface CrmDeal {
  id: number
  name: string
  pipeline_id: number
  stage_id: number
  stage_name?: string
  amount: number | null
  currency: string
  responsible_id: number | null
  contact_id: number | null
  company_id?: number | null
  updated_at: string
}

export interface CrmActivity {
  id: number
  type: string
  title: string
  body?: string
  status: string
  created_at: string
}

export interface KanbanColumn {
  stage: { id: number; name: string; color: string }
  deals: CrmDeal[]
}

/* ---------- Managers ---------- */
export const listManagers = () =>
  api<Array<{ id: number; name: string }>>('/crm/managers/')

/* ---------- Contacts ---------- */
export const listContacts = (q?: string) =>
  api<CrmContact[]>(`/crm/contacts/${q ? `?q=${encodeURIComponent(q)}` : ''}`)

export const getContact = (id: number) => api<CrmContact & { activities: CrmActivity[] }>(`/crm/contacts/${id}/`)

export const createContact = (data: Partial<CrmContact>) =>
  api<{ id: number }>('/crm/contacts/', { method: 'POST', body: data })

export const patchContact = (id: number, data: Partial<CrmContact>) =>
  api('/crm/contacts/' + id + '/', { method: 'PATCH', body: data })

export const deleteContact = (id: number) =>
  api('/crm/contacts/' + id + '/', { method: 'DELETE' })

/* ---------- Companies ---------- */
export const listCompanies = (q?: string) =>
  api<CrmCompany[]>(`/crm/companies/${q ? `?q=${encodeURIComponent(q)}` : ''}`)

export const getCompany = (id: number) => api<CrmCompany>(`/crm/companies/${id}/`)

export const createCompany = (data: Partial<CrmCompany>) =>
  api<{ id: number }>('/crm/companies/', { method: 'POST', body: data })

export const patchCompany = (id: number, data: Partial<CrmCompany>) =>
  api('/crm/companies/' + id + '/', { method: 'PATCH', body: data })

export const deleteCompany = (id: number) =>
  api('/crm/companies/' + id + '/', { method: 'DELETE' })

/* ---------- Pipelines ---------- */
export const listPipelines = () => api<CrmPipeline[]>('/crm/pipelines/')

export const createPipeline = (data: { name: string; is_default?: boolean }) =>
  api<{ id: number }>('/crm/pipelines/', { method: 'POST', body: data })

export const patchPipeline = (id: number, data: Partial<CrmPipeline>) =>
  api('/crm/pipelines/' + id + '/', { method: 'PATCH', body: data })

export const deletePipeline = (id: number) =>
  api('/crm/pipelines/' + id + '/', { method: 'DELETE' })

/* ---------- Stages ---------- */
export const listStages = (pipelineId: number) =>
  api<CrmStage[]>(`/crm/pipelines/${pipelineId}/stages/`)

export const createStage = (pipelineId: number, data: { name: string; stage_type?: string; color?: string }) =>
  api<{ id: number }>(`/crm/pipelines/${pipelineId}/stages/`, { method: 'POST', body: data })

export const patchStage = (id: number, data: Partial<CrmStage>) =>
  api('/crm/stages/' + id + '/', { method: 'PATCH', body: data })

export const deleteStage = (id: number) =>
  api('/crm/stages/' + id + '/', { method: 'DELETE' })

export const reorderStages = (pipelineId: number, stageIds: number[]) =>
  api(`/crm/pipelines/${pipelineId}/stages/reorder/`, { method: 'POST', body: stageIds })

/* ---------- Deals ---------- */
export const listDeals = (params?: Record<string, string | number>) => {
  const qs = params
    ? '?' + Object.entries(params).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join('&')
    : ''
  return api<CrmDeal[]>(`/crm/deals/${qs}`)
}

export const kanbanDeals = (pipelineId: number) =>
  api<KanbanColumn[]>(`/crm/deals/kanban/${pipelineId}/`)

export const getDeal = (id: number) =>
  api<CrmDeal & { activities: CrmActivity[] }>(`/crm/deals/${id}/`)

export const createDeal = (data: Record<string, unknown>) =>
  api<{ id: number }>('/crm/deals/', { method: 'POST', body: data })

export const patchDeal = (id: number, data: Record<string, unknown>) =>
  api('/crm/deals/' + id + '/', { method: 'PATCH', body: data })

export const moveDeal = (id: number, stageId: number) =>
  api(`/crm/deals/${id}/move/`, { method: 'PATCH', body: { stage_id: stageId } })

export const deleteDeal = (id: number) =>
  api('/crm/deals/' + id + '/', { method: 'DELETE' })

/* ---------- Activities ---------- */
export const dealActivities = (dealId: number) =>
  api<CrmActivity[]>(`/crm/deals/${dealId}/activities/`)

export const contactActivities = (contactId: number) =>
  api<CrmActivity[]>(`/crm/contacts/${contactId}/activities/`)

export const createActivity = (data: Record<string, unknown>) =>
  api<{ id: number }>('/crm/activities/', { method: 'POST', body: data })

export const patchActivity = (id: number, data: Record<string, unknown>) =>
  api('/crm/activities/' + id + '/', { method: 'PATCH', body: data })

export const deleteActivity = (id: number) =>
  api('/crm/activities/' + id + '/', { method: 'DELETE' })

/* ---------- Stats ---------- */
export const pipelineStats = (pipelineId: number) =>
  api<Array<{ stage_id: number; stage_name: string; total: number; amount: number }>>(`/crm/stats/pipeline/${pipelineId}/`)

export const managerStats = () =>
  api<Array<{ responsible_id: number | null; manager_name: string | null; total: number; amount: number }>>('/crm/stats/managers/')

/* ---------- Tasks ---------- */
export const myTasks = (status?: string) =>
  api<Array<{ id: number; activity_type: string; deal_id: number | null; contact_id: number | null; responsible_id: number | null; title: string; body: string; status: string; due_date: string | null; created_at: string }>>(`/crm/activities/tasks/${status ? `?status=${status}` : ''}`)
