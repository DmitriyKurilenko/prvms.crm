export type Role = 'owner' | 'admin' | 'manager' | 'viewer'

export interface AuditEvent {
  id: number
  user_id: number | null
  user_email: string | null
  action: string
  model_name: string
  object_id: string
  object_repr: string
  changes: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export interface AuditListResponse {
  total: number
  items: AuditEvent[]
}
export type CrmPermissionEntity = 'deals' | 'contacts' | 'companies' | 'products' | 'webforms'
export type CrmPermissionScope = 'all' | 'team' | 'own'
export type IntegrationType = 'amocrm' | 'bitrix24'
export type IntegrationMode = 'webhook' | 'oauth' | 'marketplace'
export type IntegrationStatusCode =
  | 'working'
  | 'requires_authorization'
  | 'webhook_error'
  | 'insufficient_scope'
  | 'error'
  | 'disabled'

export interface CrmEntityPermission {
  can_view: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
  scope: CrmPermissionScope
}

export type CrmPermissionMap = Record<CrmPermissionEntity, CrmEntityPermission>

export type FeatureCode =
  | 'distribution'
  | 'documents'
  | 'document_signing'
  | 'analytics'
  | 'export_pdf'
  | 'export_excel'
  | 'custom_document_templates'
  | 'api_access'
  | 'messenger_channels'
  | 'telephony'
  | 'crm_builtin'

export interface PlanFeature {
  code: FeatureCode | string
  name: string
  description: string
}

export interface PlanCatalogItem {
  id: number
  name: string
  slug: string
  description: string
  features: PlanFeature[]
  max_managers: number | null
  max_documents_per_month: number | null
  max_pipelines: number | null
  max_messengers: number | null
  max_inbound_channels: number | null
  max_signatures_per_month: number | null
  telephony_included: boolean
  max_phone_numbers: number | null
  max_phone_lines: number | null
  included_minutes: number | null
  kind: 'preset' | 'custom'
  price_monthly: number
  is_active: boolean
}

export interface AuthUser {
  id: number
  email: string
  username: string
  role: Role
  tenant_id: number
  tenant_name: string
  tenant_slug: string
  crm_permissions: CrmPermissionMap
}

export interface OrganizationMembership {
  tenant_id: number
  tenant_slug: string
  tenant_name: string
  role: Role
  joined_at: string | null
}

export interface TenantInfo {
  id: number
  name: string
  slug: string
  brand_color: string
  timezone: string
  language: string
  logo_url: string | null
  onboarding_step: number
  is_active: boolean
  is_paid: boolean
  trial_active: boolean
  trial_expired: boolean
  trial_expires_at: string | null
}

export interface TenantPlan {
  plan_name: string
  plan_slug: string
  features: FeatureCode[]
  max_managers: number | null
  max_documents_per_month: number | null
  max_pipelines: number | null
  usage: {
    managers: number
    documents: number
    pipelines: number
  }
}

export interface IntegrationConnection {
  id: number
  crm_type: IntegrationType
  name: string
  integration_mode: IntegrationMode
  is_active: boolean
  is_authorized: boolean
  last_sync_at: string | null
  last_health_check_at: string | null
  last_webhook_at: string | null
  last_error: string
  webhook_count: number
  default_webhook_url: string | null
  status_code: IntegrationStatusCode
  status_label: string
  status_detail: string
  missing_scopes: string[]
  required_scopes: string[]
  granted_scopes: string[]
  error_log_count: number
}

export interface IntegrationErrorLogEntry {
  id: number
  code: string
  title: string
  message: string
  resolution: string
  level: 'info' | 'warning' | 'error'
  details: Record<string, unknown>
  created_at: string
}

export interface OAuthStartResponse {
  connection_id: number
  crm_type: IntegrationType
  authorize_url: string
  state: string
  redirect_uri: string
  install_mode: 'oauth' | 'marketplace'
  required_scopes: string[]
}
