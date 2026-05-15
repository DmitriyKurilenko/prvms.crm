<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :modal="true"
    :style="{ width: 'min(840px, 96vw)' }"
    header="Журнал ошибок интеграции"
  >
    <p class="muted" style="margin-top: 0">Подключение: <strong>{{ connectionName }}</strong></p>
    <div v-if="!logs.length" class="muted">Ошибок пока нет.</div>
    <div v-else class="error-log-list">
      <div v-for="item in logs" :key="item.id" class="error-log-item">
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
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/datetime'
import type { IntegrationErrorLogEntry } from '@/types'

defineProps<{
  visible: boolean
  connectionName: string
  logs: IntegrationErrorLogEntry[]
}>()

defineEmits<{ 'update:visible': [boolean] }>()

const logSeverity = (level: string) => ({
  info: 'info',
  warning: 'warning',
  error: 'danger'
}[level] || 'secondary')

const formatDate = (iso: string | null) => formatDateTime(iso) || '—'
</script>

<style scoped>
.muted { color: var(--text-muted); font-size: 13px; }
.error-log-list { display: flex; flex-direction: column; gap: 10px; }
.error-log-item { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.error-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.resolution { font-size: 13px; margin-top: 4px; }
</style>
