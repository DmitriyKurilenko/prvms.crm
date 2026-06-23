import { api, getAccessToken, getTenantSlug } from './http'

/* ---------- Types ---------- */
export interface CrmContact {
  id: number
  first_name: string
  last_name: string
  phone: string
  email: string
  position?: string
  messenger_id?: string
  source?: string
  company_id: number | null
  responsible_id: number | null
  esign_agreement_signed_at?: string | null
  esign_agreement_id?: number | null
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

export interface CrmDealDocumentRef {
  id: number
  template_name: string | null
  status: string
  created_at: string
  contact_phone?: string
  signing_url?: string | null
}

export interface CrmDealChatSessionRef {
  id: number
  channel_id: number
  channel_name?: string
  channel_type?: string
  external_user_name?: string
  external_chat_id?: string
  last_message_at?: string | null
  is_active?: boolean
}

export interface CrmDeal {
  id: number
  name: string
  pipeline_id: number
  stage_id: number
  stage_name?: string
  amount: number | null
  currency: string
  source?: string
  responsible_id: number | null
  contact_id: number | null
  company_id?: number | null
  expected_close_date?: string | null
  loss_reason?: string
  documents?: CrmDealDocumentRef[]
  chat_sessions?: CrmDealChatSessionRef[]
  created_at?: string
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
    ? '?' + Object.entries(params).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    : ''
  return api<CrmDeal[]>(`/crm/deals/${qs}`)
}

export const contactDeals = (contactId: number) => listDeals({ contact_id: contactId })

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

/* ---------- Calendar (Фаза 9) ---------- */
export interface CrmCalendarTask {
  id: number
  activity_type: string
  deal_id: number | null
  contact_id: number | null
  responsible_id: number | null
  title: string
  body: string
  status: string
  due_date: string | null
  recurrence_rule: string
  remind_at: string | null
  reminder_sent_at: string | null
  created_at: string
}

export const calendarActivities = (dateFrom: string, dateTo: string) =>
  api<CrmCalendarTask[]>(`/crm/activities/calendar/?date_from=${dateFrom}&date_to=${dateTo}`)

/* ---------- Products (catalog) ---------- */
export interface CrmProduct {
  id: number
  name: string
  sku: string
  category_id: number | null
  unit: string
  price: number
  currency: string
  vat_rate: number
  description: string
  is_active: boolean
  created_at: string
}

export interface CrmDealItem {
  id: number
  product_id: number
  name: string
  quantity: number
  price: number
  discount_percent: number
  vat_rate: number
  line_subtotal: number
  line_vat: number
  line_total: number
}

export interface CrmDealItems {
  items: CrmDealItem[]
  subtotal: number
  vat: number
  total: number
  has_items: boolean
}

export const listProducts = (q?: string) =>
  api<CrmProduct[]>(`/crm/products/${q ? `?q=${encodeURIComponent(q)}` : ''}`)

export const createProduct = (data: Partial<CrmProduct>) =>
  api<{ id: number }>('/crm/products/', { method: 'POST', body: data })

export const patchProduct = (id: number, data: Partial<CrmProduct>) =>
  api('/crm/products/' + id + '/', { method: 'PATCH', body: data })

export const deleteProduct = (id: number) =>
  api<{ detail: string }>('/crm/products/' + id + '/', { method: 'DELETE' })

export const listDealItems = (dealId: number) =>
  api<CrmDealItems>(`/crm/deals/${dealId}/items/`)

export const addDealItem = (
  dealId: number,
  data: { product_id: number; quantity: number; price?: number; discount_percent?: number; vat_rate?: number },
) => api<{ item_id: number; deal_amount: number }>(`/crm/deals/${dealId}/items/`, { method: 'POST', body: data })

export const deleteDealItem = (dealId: number, itemId: number) =>
  api<{ detail: string; deal_amount: number }>(`/crm/deals/${dealId}/items/${itemId}/`, { method: 'DELETE' })

/* ---------- Web forms ---------- */
export interface CrmWebFormField {
  key: string
  label: string
  type: string
  required: boolean
  options?: string[]
}

export interface CrmWebForm {
  id: number
  name: string
  public_token: string
  fields_schema: CrmWebFormField[]
  pipeline_id: number
  stage_id: number
  source: string
  auto_distribute: boolean
  success_message: string
  allowed_origins: string[]
  is_active: boolean
  submissions_count: number
  created_at: string
  embed_snippet: string
}

export const listWebForms = () => api<CrmWebForm[]>('/crm/webforms/')

export const createWebForm = (data: Record<string, unknown>) =>
  api<CrmWebForm>('/crm/webforms/', { method: 'POST', body: data })

export const patchWebForm = (id: number, data: Record<string, unknown>) =>
  api('/crm/webforms/' + id + '/', { method: 'PATCH', body: data })

export const deleteWebForm = (id: number) =>
  api<{ detail: string }>('/crm/webforms/' + id + '/', { method: 'DELETE' })

/* ---------- Tags & segments ---------- */
export interface CrmTag {
  id: number
  name: string
  color: string
}

export const listTags = () => api<CrmTag[]>('/crm/tags/')

export const createTag = (data: { name: string; color?: string }) =>
  api<{ id: number }>('/crm/tags/', { method: 'POST', body: data })

export const patchTag = (id: number, data: Partial<CrmTag>) =>
  api('/crm/tags/' + id + '/', { method: 'PATCH', body: data })

export const deleteTag = (id: number) =>
  api<{ detail: string }>('/crm/tags/' + id + '/', { method: 'DELETE' })

export const setDealTags = (dealId: number, tagIds: number[]) =>
  api(`/crm/deals/${dealId}/tags/`, { method: 'PATCH', body: { tag_ids: tagIds } })

export const setContactTags = (contactId: number, tagIds: number[]) =>
  api(`/crm/contacts/${contactId}/tags/`, { method: 'PATCH', body: { tag_ids: tagIds } })

/* ---------- Automation rules ---------- */
export interface CrmAutomationRule {
  id: number
  name: string
  trigger: string
  conditions: Record<string, unknown>
  action: Record<string, unknown>
  is_active: boolean
  priority: number
  created_at: string
}

export const listAutomationRules = () => api<CrmAutomationRule[]>('/crm/automation/rules/')

export const createAutomationRule = (data: Record<string, unknown>) =>
  api<{ id: number }>('/crm/automation/rules/', { method: 'POST', body: data })

export const patchAutomationRule = (id: number, data: Record<string, unknown>) =>
  api('/crm/automation/rules/' + id + '/', { method: 'PATCH', body: data })

export const deleteAutomationRule = (id: number) =>
  api<{ detail: string }>('/crm/automation/rules/' + id + '/', { method: 'DELETE' })

/* ---------- Analytics & sales targets (Фаза 10) ---------- */
export interface FunnelStage {
  stage_id: number
  stage_name: string
  stage_type: string
  count: number
  amount: number
  share: number
}
export interface FunnelData {
  stages: FunnelStage[]
  summary: { total: number; won: number; lost: number; open: number; win_rate: number }
}
export interface LossReasonRow {
  loss_reason: string
  count: number
  amount: number
}
export interface ForecastData {
  open_total_amount: number
  open_count: number
  period_forecast_amount: number
  period_forecast_count: number
}
export interface SalesTarget {
  id: number
  period: string
  responsible_id: number
  manager_name: string
  target_amount: number | null
  target_count: number | null
}
export interface TargetProgressRow {
  responsible_id: number
  manager_name: string
  target_amount: number | null
  actual_amount: number
  amount_pct: number | null
  target_count: number | null
  actual_count: number
  count_pct: number | null
}

function rangeQs(dateFrom?: string, dateTo?: string): string {
  const p = new URLSearchParams()
  if (dateFrom) p.set('date_from', dateFrom)
  if (dateTo) p.set('date_to', dateTo)
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const funnel = (pipelineId: number, dateFrom?: string, dateTo?: string) => {
  const p = new URLSearchParams({ pipeline_id: String(pipelineId) })
  if (dateFrom) p.set('date_from', dateFrom)
  if (dateTo) p.set('date_to', dateTo)
  return api<FunnelData>(`/crm/analytics/funnel/?${p.toString()}`)
}
export const lossReasons = (dateFrom?: string, dateTo?: string) =>
  api<LossReasonRow[]>(`/crm/analytics/loss-reasons/${rangeQs(dateFrom, dateTo)}`)
export const forecast = (dateFrom?: string, dateTo?: string) =>
  api<ForecastData>(`/crm/analytics/forecast/${rangeQs(dateFrom, dateTo)}`)

export const listTargets = (period?: string) =>
  api<SalesTarget[]>(`/crm/targets/${period ? `?period=${period}` : ''}`)
export const upsertTarget = (data: { period: string; responsible_id: number; target_amount?: number | null; target_count?: number | null }) =>
  api<{ id: number }>('/crm/targets/', { method: 'POST', body: data })
export const deleteTarget = (id: number) =>
  api<{ detail: string }>('/crm/targets/' + id + '/', { method: 'DELETE' })
export const targetProgress = (period: string) =>
  api<TargetProgressRow[]>(`/crm/analytics/target-progress/?period=${period}`)

/* ---------- Import / export / merge ---------- */
export type DataEntity = 'contacts' | 'companies'

export interface CrmImportPreview {
  headers: string[]
  sample: Record<string, string>[]
  total_rows: number
  suggested_mapping: Record<string, string>
  allowed_fields: string[]
}

export interface CrmImportJob {
  id: number
  entity: DataEntity
  status: 'pending' | 'running' | 'done' | 'failed'
  total: number
  processed: number
  created: number
  updated: number
  errors: { row: number; message: string }[]
  created_at: string
}

export interface CrmDuplicateGroup {
  key_type: string
  key: string
  items: { id: number; label: string }[]
}

export const importPreview = (entity: DataEntity, file: File) => {
  const form = new FormData()
  form.append('entity', entity)
  form.append('file', file)
  return api<CrmImportPreview>('/crm/import/preview/', { method: 'POST', body: form })
}

export const importRun = (entity: DataEntity, file: File, mapping: Record<string, string>) => {
  const form = new FormData()
  form.append('entity', entity)
  form.append('mapping', JSON.stringify(mapping))
  form.append('file', file)
  return api<{ job_id: number; total: number }>('/crm/import/run/', { method: 'POST', body: form })
}

export const importJobStatus = (jobId: number) =>
  api<CrmImportJob>('/crm/import/jobs/' + jobId + '/')

export const listDuplicates = (entity: DataEntity) =>
  api<CrmDuplicateGroup[]>('/crm/duplicates/' + entity + '/')

export const mergeRecords = (entity: DataEntity, primaryId: number, mergedIds: number[]) =>
  api('/crm/merge/' + entity + '/', { method: 'POST', body: { primary_id: primaryId, merged_ids: mergedIds } })

/** Скачивание CSV-экспорта (HttpResponse-файл, паттерн AuditView). */
export async function downloadExport(entity: DataEntity): Promise<void> {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  const res = await fetch(`${apiUrl}/crm/export/${entity}/`, {
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      ...(getTenantSlug() ? { 'X-Tenant-Slug': getTenantSlug()! } : {}),
    },
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${entity}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
