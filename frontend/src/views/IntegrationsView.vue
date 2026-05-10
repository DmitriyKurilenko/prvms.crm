<template>
  <section class="integrations-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Интеграции CRM</h1>
    </div>

    <div class="surface-card setup-card">
      <h3>Подключение внешней CRM</h3>
      <p class="muted">
        Рекомендуемый путь: установка приложения из маркетплейса (OAuth). Быстрый старт: webhook/manual credentials.
      </p>

      <div class="mode-switch">
        <PButton
          label="Рекомендуемый: приложение"
          size="small"
          :outlined="setupMode !== 'marketplace'"
          @click="setupMode = 'marketplace'"
        />
        <PButton
          label="Быстрый старт: webhook"
          size="small"
          :outlined="setupMode !== 'webhook'"
          @click="setupMode = 'webhook'"
        />
      </div>

      <template v-if="setupMode === 'marketplace'">
        <div class="grid">
          <div class="field">
            <label class="field-label">Название подключения</label>
            <PInputText v-model="marketplaceName" placeholder="Основная интеграция" />
          </div>
        </div>
        <div class="actions-row">
              <PButton
                label="Установить amoCRM приложение"
                icon="pi pi-external-link"
                @click="startInstall('amocrm', 'marketplace')"
                :loading="installing === 'amocrm:marketplace'"
                :disabled="!isFeatureEnabledForCrm('amocrm')"
              />
              <PButton
                label="Установить Битрикс24 приложение"
                icon="pi pi-external-link"
                severity="secondary"
                @click="startInstall('bitrix24', 'marketplace')"
                :loading="installing === 'bitrix24:marketplace'"
                :disabled="!isFeatureEnabledForCrm('bitrix24')"
              />
            </div>
            <div class="actions-row">
              <PButton
                text
                label="OAuth без маркетплейса (amoCRM)"
                @click="startInstall('amocrm', 'oauth')"
                :loading="installing === 'amocrm:oauth'"
                :disabled="!isFeatureEnabledForCrm('amocrm')"
              />
              <PButton
                text
                label="OAuth без маркетплейса (Битрикс24)"
                @click="startInstall('bitrix24', 'oauth')"
                :loading="installing === 'bitrix24:oauth'"
                :disabled="!isFeatureEnabledForCrm('bitrix24')"
              />
            </div>
          </template>

      <template v-else>
        <form class="webhook-form" @submit.prevent="createWebhookConnection">
          <div class="grid">
            <div class="field">
              <label class="field-label">CRM</label>
              <PSelect
                v-model="quickForm.crm_type"
                :options="crmOptions"
                optionLabel="label"
                optionValue="value"
              />
            </div>
            <div class="field">
              <label class="field-label">Название подключения</label>
              <PInputText v-model="quickForm.name" placeholder="CRM webhook" />
            </div>
          </div>

          <div class="grid" v-if="quickForm.crm_type === 'amocrm'">
            <div class="field">
              <label class="field-label">Base URL</label>
              <PInputText v-model="quickForm.amocrm.base_url" placeholder="https://example.amocrm.ru" />
            </div>
            <div class="field">
              <label class="field-label">Subdomain (опц.)</label>
              <PInputText v-model="quickForm.amocrm.subdomain" placeholder="example" />
            </div>
            <div class="field">
              <label class="field-label">Access Token</label>
              <PInputText v-model="quickForm.amocrm.access_token" placeholder="token" />
            </div>
            <div class="field">
              <label class="field-label">Webhook HMAC Secret (опц.)</label>
              <PInputText v-model="quickForm.amocrm.webhook_hmac_secret" placeholder="hmac secret" />
            </div>
          </div>

          <div class="grid" v-else>
            <div class="field">
              <label class="field-label">Webhook URL</label>
              <PInputText v-model="quickForm.bitrix24.webhook_url" placeholder="https://portal.bitrix24.ru/rest/1/xyz/" />
            </div>
            <div class="field">
              <label class="field-label">Base URL (для OAuth, опц.)</label>
              <PInputText v-model="quickForm.bitrix24.base_url" placeholder="https://portal.bitrix24.ru" />
            </div>
            <div class="field">
              <label class="field-label">Access Token (опц.)</label>
              <PInputText v-model="quickForm.bitrix24.access_token" placeholder="token" />
            </div>
            <div class="field">
              <label class="field-label">User ID (опц.)</label>
              <PInputText v-model="quickForm.bitrix24.user_id" placeholder="1" />
            </div>
            <div class="field">
              <label class="field-label">Application Token (опц.)</label>
              <PInputText v-model="quickForm.bitrix24.application_token" placeholder="app token" />
            </div>
          </div>

          <div class="actions-row">
            <PButton
              type="submit"
              label="Создать webhook-подключение"
              icon="pi pi-plus"
              :loading="creatingWebhook"
              :disabled="!isFeatureEnabledForCrm(quickForm.crm_type)"
            />
          </div>
          <p v-if="!isFeatureEnabledForCrm(quickForm.crm_type)" class="muted">
            Эта интеграция недоступна на текущем тарифе.
          </p>
        </form>
      </template>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="successMessage" class="success">{{ successMessage }}</p>
    </div>

    <div class="surface-card table-card">
      <PDataTable :value="connections" :loading="loading" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
        <PColumn field="name" header="Название" />
        <PColumn header="CRM">
          <template #body="{ data }">
            {{ crmLabel(data.crm_type) }}
          </template>
        </PColumn>
        <PColumn header="Режим">
          <template #body="{ data }">
            {{ modeLabel(data.integration_mode) }}
          </template>
        </PColumn>
        <PColumn header="Статус">
          <template #body="{ data }">
            <div class="status-cell">
              <PTag :value="data.status_label" :severity="statusSeverity(data.status_code)" />
              <small>{{ data.status_detail }}</small>
              <small v-if="!isConnectionFeatureEnabled(data)" class="locked-note">
                Недоступно на текущем тарифе
              </small>
            </div>
          </template>
        </PColumn>
        <PColumn header="Scope">
          <template #body="{ data }">
            <div class="status-cell">
              <small v-if="data.missing_scopes?.length">Не хватает: {{ data.missing_scopes.join(', ') }}</small>
              <small v-else-if="data.required_scopes?.length">OK: {{ data.required_scopes.join(', ') }}</small>
              <small v-else>—</small>
            </div>
          </template>
        </PColumn>
        <PColumn header="Webhook URL">
          <template #body="{ data }">
            <code class="webhook-code" :title="data.default_webhook_url || ''">{{ data.default_webhook_url || '—' }}</code>
          </template>
        </PColumn>
        <PColumn header="Последняя активность">
          <template #body="{ data }">
            <div class="status-cell">
              <small>sync: {{ formatDate(data.last_sync_at) }}</small>
              <small>health: {{ formatDate(data.last_health_check_at) }}</small>
              <small>webhook: {{ formatDate(data.last_webhook_at) }}</small>
            </div>
          </template>
        </PColumn>
        <PColumn header="">
          <template #body="{ data }">
            <div class="actions-cell">
              <PButton
                icon="pi pi-check-circle"
                text
                size="small"
                :title="actionTitle(data.crm_type, 'Проверить')"
                @click="runTest(data)"
                :loading="busyKey === `test:${data.id}`"
                :disabled="!isConnectionFeatureEnabled(data)"
              />
              <PButton
                icon="pi pi-sync"
                text
                size="small"
                :title="actionTitle(data.crm_type, 'Синхронизировать менеджеров')"
                @click="runSync(data)"
                :loading="busyKey === `sync:${data.id}`"
                :disabled="!isConnectionFeatureEnabled(data)"
              />
              <PButton
                icon="pi pi-refresh"
                text
                size="small"
                :title="actionTitle(data.crm_type, 'Переавторизовать')"
                @click="runReconnect(data)"
                :loading="busyKey === `reconnect:${data.id}`"
                :disabled="!isConnectionFeatureEnabled(data)"
              />
              <PButton
                icon="pi pi-exclamation-circle"
                text
                size="small"
                :title="actionTitle(data.crm_type, 'Журнал ошибок')"
                @click="openErrors(data)"
                :badge="String(data.error_log_count || 0)"
                :disabled="!isConnectionFeatureEnabled(data)"
              />
              <PButton
                icon="pi pi-trash"
                text
                size="small"
                severity="danger"
                :title="actionTitle(data.crm_type, 'Удалить')"
                @click="removeConnection(data)"
                :loading="busyKey === `delete:${data.id}`"
                :disabled="!isConnectionFeatureEnabled(data)"
              />
            </div>
          </template>
        </PColumn>
      </PDataTable>
    </div>

    <PDialog v-model:visible="errorsDialogVisible" :modal="true" :style="{ width: 'min(840px, 96vw)' }" header="Журнал ошибок интеграции">
      <p class="muted" style="margin-top: 0">Подключение: <strong>{{ errorsDialogConnectionName }}</strong></p>
      <div v-if="!errorLogs.length" class="muted">Ошибок пока нет.</div>
      <div v-else class="error-log-list">
        <div v-for="item in errorLogs" :key="item.id" class="error-log-item">
          <div class="error-head">
            <PTag :value="item.level.toUpperCase()" :severity="logSeverity(item.level)" />
            <strong>{{ item.title }}</strong>
            <small>{{ formatDate(item.created_at) }}</small>
          </div>
          <div class="muted">{{ item.message }}</div>
          <div v-if="item.resolution" class="resolution">Что сделать: {{ item.resolution }}</div>
        </div>
      </div>
    </PDialog>
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
import { formatDateTime } from '@/utils/datetime'
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

const logSeverity = (level: string) => ({
  info: 'info',
  warning: 'warning',
  error: 'danger'
}[level] || 'secondary')

const formatDate = (iso: string | null) => formatDateTime(iso) || '—'

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
