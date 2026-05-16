<template>
  <div class="surface-card table-card">
    <PDataTable v-responsive-table :value="connections" :loading="loading" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
      <PColumn field="name" header="Название" />
      <PColumn header="CRM">
        <template #body="{ data }">{{ crmLabel(data.crm_type) }}</template>
      </PColumn>
      <PColumn header="Режим">
        <template #body="{ data }">{{ modeLabel(data.integration_mode) }}</template>
      </PColumn>
      <PColumn header="Статус">
        <template #body="{ data }">
          <div class="status-cell">
            <PTag :value="data.status_label" :severity="statusSeverity(data.status_code)" />
            <small>{{ data.status_detail }}</small>
            <small v-if="!isConnectionEnabled(data)" class="locked-note">
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
              @click="$emit('test', data)"
              :loading="busyKey === `test:${data.id}`"
              :disabled="!isConnectionEnabled(data)"
            />
            <PButton
              icon="pi pi-sync"
              text
              size="small"
              :title="actionTitle(data.crm_type, 'Синхронизировать менеджеров')"
              @click="$emit('sync', data)"
              :loading="busyKey === `sync:${data.id}`"
              :disabled="!isConnectionEnabled(data)"
            />
            <PButton
              icon="pi pi-refresh"
              text
              size="small"
              :title="actionTitle(data.crm_type, 'Переавторизовать')"
              @click="$emit('reconnect', data)"
              :loading="busyKey === `reconnect:${data.id}`"
              :disabled="!isConnectionEnabled(data)"
            />
            <PButton
              icon="pi pi-exclamation-circle"
              text
              size="small"
              :title="actionTitle(data.crm_type, 'Журнал ошибок')"
              @click="$emit('openErrors', data)"
              :badge="String(data.error_log_count || 0)"
              :disabled="!isConnectionEnabled(data)"
            />
            <PButton
              icon="pi pi-trash"
              text
              size="small"
              severity="danger"
              :title="actionTitle(data.crm_type, 'Удалить')"
              @click="$emit('remove', data)"
              :loading="busyKey === `delete:${data.id}`"
              :disabled="!isConnectionEnabled(data)"
            />
          </div>
        </template>
      </PColumn>
    </PDataTable>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/datetime'
import type {
  IntegrationConnection,
  IntegrationMode,
  IntegrationStatusCode,
  IntegrationType,
} from '@/types'

defineProps<{
  connections: IntegrationConnection[]
  loading: boolean
  busyKey: string
  isConnectionEnabled: (connection: IntegrationConnection) => boolean
  actionTitle: (crmType: IntegrationType, title: string) => string
  crmLabel: (type: IntegrationType) => string
  modeLabel: (mode: IntegrationMode) => string
  statusSeverity: (status: IntegrationStatusCode) => string
}>()

defineEmits<{
  test: [IntegrationConnection]
  sync: [IntegrationConnection]
  reconnect: [IntegrationConnection]
  openErrors: [IntegrationConnection]
  remove: [IntegrationConnection]
}>()

const formatDate = (iso: string | null) => formatDateTime(iso) || '—'
</script>

<style scoped>
.table-card { padding: 0; overflow: hidden; }
.status-cell { display: flex; flex-direction: column; gap: 2px; }
.status-cell small { color: var(--text-muted); font-size: 12px; }
.locked-note { color: var(--orange-500, #d97706) !important; }
.actions-cell { display: flex; gap: 2px; }
.webhook-code { font-size: 11px; word-break: break-all; }
</style>
