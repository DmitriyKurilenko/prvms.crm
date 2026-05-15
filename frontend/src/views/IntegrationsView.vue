<template>
  <section class="integrations-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Интеграции CRM</h1>
    </div>

    <IntegrationSetupCard
      v-model:setup-mode="setupMode"
      v-model:marketplace-name="marketplaceName"
      :form="quickForm"
      :crm-options="crmOptions"
      :installing="installing"
      :creating-webhook="creatingWebhook"
      :error-message="errorMessage"
      :success-message="successMessage"
      :is-feature-enabled="isFeatureEnabledForCrm"
      @install="startInstall"
      @submit-webhook="createWebhookConnection"
    />

    <ConnectionsTable
      :connections="connections"
      :loading="loading"
      :busy-key="busyKey"
      :is-connection-enabled="isConnectionFeatureEnabled"
      :action-title="actionTitle"
      :crm-label="crmLabel"
      :mode-label="modeLabel"
      :status-severity="statusSeverity"
      @test="runTest"
      @sync="runSync"
      @reconnect="runReconnect"
      @open-errors="openErrors"
      @remove="removeConnection"
    />

    <IntegrationErrorsDialog
      v-model:visible="errorsDialogVisible"
      :connection-name="errorsDialogConnectionName"
      :logs="errorLogs"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createConnection,
  deleteConnection,
  listConnectionErrors,
  listConnections,
  reconnectConnection,
  startMarketplaceInstall,
  startOAuth,
  syncConnectionUsers,
  testConnection
} from '@/api/integrations'
import { useTenantStore } from '@/stores/tenant'
import IntegrationSetupCard from '@/components/IntegrationSetupCard.vue'
import ConnectionsTable from '@/components/ConnectionsTable.vue'
import IntegrationErrorsDialog from '@/components/IntegrationErrorsDialog.vue'
import type {
  IntegrationConnection,
  IntegrationErrorLogEntry,
  IntegrationMode,
  IntegrationStatusCode,
  IntegrationType
} from '@/types'

const tenantStore = useTenantStore()
const setupMode = ref<'marketplace' | 'webhook'>('marketplace')
const loading = ref(false)
const connections = ref<IntegrationConnection[]>([])
const installing = ref('')
const creatingWebhook = ref(false)
const busyKey = ref('')
const errorMessage = ref('')
const successMessage = ref('')

const errorsDialogVisible = ref(false)
const errorsDialogConnectionName = ref('')
const errorLogs = ref<IntegrationErrorLogEntry[]>([])

const crmOptions = [
  { value: 'amocrm', label: 'amoCRM' },
  { value: 'bitrix24', label: 'Битрикс24' }
]

const marketplaceName = ref('Основная интеграция')

const quickForm = reactive({
  crm_type: 'amocrm' as IntegrationType,
  name: 'CRM webhook',
  amocrm: {
    base_url: '',
    subdomain: '',
    access_token: '',
    webhook_hmac_secret: ''
  },
  bitrix24: {
    webhook_url: '',
    base_url: '',
    access_token: '',
    user_id: '',
    application_token: ''
  }
})

const compact = (payload: Record<string, unknown>) => {
  const result: Record<string, unknown> = {}
  Object.entries(payload).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && !value.trim()) return
    result[key] = value
  })
  return result
}

const crmFeatureName = (crmType: IntegrationType): 'crm_amocrm' | 'crm_bitrix24' => (
  crmType === 'amocrm' ? 'crm_amocrm' : 'crm_bitrix24'
)
const crmFeatureLabel = (crmType: IntegrationType) => (crmType === 'amocrm' ? 'Интеграция с amoCRM' : 'Интеграция с Битрикс24')
const isFeatureEnabledForCrm = (crmType: IntegrationType) => tenantStore.hasFeature(crmFeatureName(crmType))
const isConnectionFeatureEnabled = (connection: IntegrationConnection) => isFeatureEnabledForCrm(connection.crm_type)
const actionTitle = (crmType: IntegrationType, title: string) => (
  isFeatureEnabledForCrm(crmType)
    ? title
    : `Недоступно на текущем тарифе: ${crmFeatureLabel(crmType)}`
)

const ensureFeatureAccess = (crmType: IntegrationType) => {
  if (isFeatureEnabledForCrm(crmType)) return true
  errorMessage.value = `Недоступно на текущем тарифе: ${crmFeatureLabel(crmType)}.`
  successMessage.value = ''
  return false
}

const loadConnections = async () => {
  loading.value = true
  try {
    connections.value = await listConnections()
  } catch {
    errorMessage.value = 'Не удалось загрузить список интеграций.'
  } finally {
    loading.value = false
  }
}

const startInstall = async (crmType: IntegrationType, mode: 'oauth' | 'marketplace') => {
  if (!ensureFeatureAccess(crmType)) return
  errorMessage.value = ''
  successMessage.value = ''
  installing.value = `${crmType}:${mode}`
  try {
    const name = marketplaceName.value.trim() || (crmType === 'amocrm' ? 'amoCRM app' : 'Bitrix24 app')
    const payload = { name, install_mode: mode, redirect_uri: undefined }
    const response = mode === 'marketplace'
      ? await startMarketplaceInstall(crmType, payload)
      : await startOAuth(crmType, payload)
    successMessage.value = 'Перенаправляем в CRM для подтверждения доступа...'
    window.location.href = response.authorize_url
  } catch (error: any) {
    errorMessage.value = error?.data?.detail || 'Не удалось начать установку интеграции.'
  } finally {
    installing.value = ''
  }
}

const createWebhookConnection = async () => {
  if (!ensureFeatureAccess(quickForm.crm_type)) return
  errorMessage.value = ''
  successMessage.value = ''
  creatingWebhook.value = true
  try {
    const credentials = quickForm.crm_type === 'amocrm'
      ? compact({
          base_url: quickForm.amocrm.base_url,
          subdomain: quickForm.amocrm.subdomain,
          access_token: quickForm.amocrm.access_token,
          webhook_hmac_secret: quickForm.amocrm.webhook_hmac_secret
        })
      : compact({
          webhook_url: quickForm.bitrix24.webhook_url,
          base_url: quickForm.bitrix24.base_url,
          access_token: quickForm.bitrix24.access_token,
          user_id: quickForm.bitrix24.user_id,
          application_token: quickForm.bitrix24.application_token
        })

    await createConnection({
      crm_type: quickForm.crm_type,
      name: quickForm.name.trim() || 'CRM webhook',
      credentials,
      integration_mode: 'webhook'
    })
    successMessage.value = 'Webhook-подключение создано.'
    await loadConnections()
  } catch (error: any) {
    errorMessage.value = error?.data?.detail || 'Не удалось создать webhook-подключение.'
  } finally {
    creatingWebhook.value = false
  }
}

const withBusy = async (key: string, fn: () => Promise<void>) => {
  if (busyKey.value) return
  busyKey.value = key
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await fn()
    await loadConnections()
  } catch (error: any) {
    errorMessage.value = error?.data?.detail || 'Операция завершилась ошибкой.'
  } finally {
    busyKey.value = ''
  }
}

const runTest = async (connection: IntegrationConnection) => {
  if (!ensureFeatureAccess(connection.crm_type)) return
  const connectionId = connection.id
  await withBusy(`test:${connectionId}`, async () => {
    const result = await testConnection(connectionId)
    if (result.connection.ok && result.webhook.ok) {
      successMessage.value = `Проверка успешна: ${result.status_label}`
    } else {
      successMessage.value = `Проверка завершена: ${result.status_label} — ${result.status_detail}`
    }
  })
}

const runSync = async (connection: IntegrationConnection) => {
  if (!ensureFeatureAccess(connection.crm_type)) return
  const connectionId = connection.id
  await withBusy(`sync:${connectionId}`, async () => {
    await syncConnectionUsers(connectionId)
    successMessage.value = 'Синхронизация менеджеров запущена.'
  })
}

const runReconnect = async (connection: IntegrationConnection) => {
  if (!ensureFeatureAccess(connection.crm_type)) return
  const connectionId = connection.id
  await withBusy(`reconnect:${connectionId}`, async () => {
    await reconnectConnection(connectionId)
    successMessage.value = 'Переавторизация завершена.'
  })
}

const removeConnection = async (connection: IntegrationConnection) => {
  if (!ensureFeatureAccess(connection.crm_type)) return
  const connectionId = connection.id
  await withBusy(`delete:${connectionId}`, async () => {
    await deleteConnection(connectionId)
    successMessage.value = 'Подключение удалено.'
  })
}

const openErrors = async (connection: IntegrationConnection) => {
  if (!ensureFeatureAccess(connection.crm_type)) return
  errorMessage.value = ''
  successMessage.value = ''
  errorsDialogConnectionName.value = connection.name
  errorLogs.value = await listConnectionErrors(connection.id)
  errorsDialogVisible.value = true
}

const crmLabel = (type: IntegrationType) => (type === 'amocrm' ? 'amoCRM' : 'Битрикс24')
const modeLabel = (mode: IntegrationMode) => ({
  marketplace: 'Маркетплейс',
  oauth: 'OAuth',
  webhook: 'Webhook/manual'
}[mode] || mode)

const statusSeverity = (status: IntegrationStatusCode) => ({
  working: 'success',
  requires_authorization: 'warning',
  webhook_error: 'danger',
  insufficient_scope: 'warning',
  error: 'danger',
  disabled: 'secondary'
}[status] || 'info')

onMounted(async () => {
  await tenantStore.ensureLoaded()
  await loadConnections()
})
</script>

<style scoped>
.setup-card,
.table-card {
  padding: 16px;
  margin-bottom: 12px;
}

.setup-card h3 {
  margin: 0 0 6px;
}

.muted {
  color: var(--text-muted);
}

.mode-switch {
  display: flex;
  gap: 8px;
  margin: 12px 0;
  flex-wrap: wrap;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 0.85rem;
  font-weight: 600;
}

.webhook-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.actions-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.error {
  margin-top: 12px;
  color: var(--danger);
}

.success {
  margin-top: 12px;
  color: #16a34a;
}

.status-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-cell small {
  color: var(--text-muted);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.locked-note {
  color: #9a3412;
}

.webhook-code {
  font-size: 0.75rem;
  max-width: 220px;
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions-cell {
  display: flex;
  align-items: center;
  gap: 2px;
}

.error-log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 60vh;
  overflow-y: auto;
}

.error-log-item {
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.error-head {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.resolution {
  font-weight: 600;
}
</style>
