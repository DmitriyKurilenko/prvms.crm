<template>
  <section class="audit-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Журнал действий</h1>
      <PButton label="Экспорт CSV" icon="pi pi-download" size="small" @click="exportCsv" />
    </div>

    <div class="surface-card filter-bar">
      <PSelect
        v-model="filters.action"
        :options="actionOptions"
        placeholder="Действие"
        showClear
        style="min-width: 150px"
      />
      <PSelect
        v-model="filters.user_id"
        :options="userOptions"
        optionLabel="email"
        optionValue="id"
        placeholder="Пользователь"
        showClear
        style="min-width: 200px"
      />
      <div class="date-field">
        <span class="date-label">Дата с</span>
        <PInputText v-model="filters.date_from" type="date" style="width: 150px" />
      </div>
      <div class="date-field">
        <span class="date-label">Дата по</span>
        <PInputText v-model="filters.date_to" type="date" style="width: 150px" />
      </div>
      <PButton label="Применить" size="small" @click="load" />
      <PButton label="Сбросить" severity="secondary" size="small" @click="resetFilters" />
    </div>

    <div class="surface-card" style="padding: 16px">
      <PDataTable
        :value="events"
        stripedRows
        :paginator="true"
        :rows="20"
        :rowsPerPageOptions="[20, 50, 100]"
        @rowClick="onRowClick"
        rowHover
      >
        <template #empty>Нет событий</template>
        <PColumn field="created_at" header="Дата" style="width: 170px">
          <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
        </PColumn>
        <PColumn field="user_email" header="Пользователь">
          <template #body="{ data }">{{ data.user_email || '—' }}</template>
        </PColumn>
        <PColumn field="action" header="Действие" style="width: 140px">
          <template #body="{ data }">
            <PTag :value="actionLabel(data.action)" :severity="actionSeverity(data.action)" />
          </template>
        </PColumn>
        <PColumn field="model_name" header="Объект" style="width: 130px" />
        <PColumn field="object_repr" header="Запись" />
      </PDataTable>
    </div>

    <AuditDiff v-if="selected" :changes="selected.changes || {}" style="margin-top: 12px" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import AuditDiff from '@/components/AuditDiff.vue'
import { formatDateTime } from '@/utils/datetime'
import type { AuditEvent, AuditListResponse } from '@/types'

const events = ref<AuditEvent[]>([])
const selected = ref<AuditEvent | null>(null)
const userOptions = ref<Array<{ id: number; email: string }>>([])

const filters = reactive({
  action: null as string | null,
  user_id: null as number | null,
  date_from: '',
  date_to: '',
})

const actionOptions = [
  'create', 'update', 'delete', 'login', 'invite', 'sign', 'distribute', 'sync', 'export',
]

function actionLabel(a: string): string {
  const map: Record<string, string> = {
    create: 'Создание', update: 'Изменение', delete: 'Удаление',
    login: 'Вход', invite: 'Приглашение', sign: 'Подписание',
    distribute: 'Распределение', sync: 'Синхронизация', export: 'Экспорт',
  }
  return map[a] || a
}

function actionSeverity(a: string): 'danger' | 'success' | 'info' | 'warn' | undefined {
  if (a === 'delete') return 'danger'
  if (a === 'create') return 'success'
  if (a === 'login') return 'info'
  return undefined
}

function formatDate(iso: string): string {
  return formatDateTime(iso)
}

function buildQuery(): Record<string, string | number> {
  const q: Record<string, string | number> = { limit: 500, offset: 0 }
  if (filters.action) q.action = filters.action
  if (filters.user_id != null) q.user_id = filters.user_id
  if (filters.date_from) q.date_from = filters.date_from
  if (filters.date_to) q.date_to = filters.date_to
  return q
}

async function load() {
  selected.value = null
  const res: AuditListResponse = await api('/audit/events/', { query: buildQuery() })
  events.value = res.items
}

function onRowClick(e: { data: AuditEvent }) {
  selected.value = selected.value?.id === e.data.id ? null : e.data
}

function resetFilters() {
  filters.action = null
  filters.user_id = null
  filters.date_from = ''
  filters.date_to = ''
  load()
}

async function exportCsv() {
  const params = new URLSearchParams()
  if (filters.action) params.set('action', filters.action)
  if (filters.user_id != null) params.set('user_id', String(filters.user_id))
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  const qs = params.toString()
  const url = `${apiUrl}/audit/events/export/${qs ? '?' + qs : ''}`

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      ...(getTenantSlug() ? { 'X-Tenant-Slug': getTenantSlug()! } : {}),
    },
    credentials: 'include',
  })
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'audit_events.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(async () => {
  try {
    const users = await api('/users/') as Array<{ id: number; email: string }>
    userOptions.value = users.map((u) => ({ id: u.id, email: u.email }))
  } catch {
    // non-critical: filter by user simply won't populate
  }
  await load()
})
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
  padding: 12px 16px;
  margin-bottom: 12px;
}

.date-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.date-label {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
