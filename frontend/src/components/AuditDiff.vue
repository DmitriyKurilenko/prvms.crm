<template>
  <div class="surface-card diff-panel">
    <h4 style="margin: 0 0 10px">Изменения</h4>
    <table v-if="diffRows.length" class="diff-table">
      <thead>
        <tr>
          <th>Поле</th>
          <th class="diff-old-head">Было</th>
          <th class="diff-new-head">Стало</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in diffRows" :key="row.field">
          <td class="diff-field">{{ row.field }}</td>
          <td class="diff-old">{{ display(row.before) }}</td>
          <td class="diff-new">{{ display(row.after) }}</td>
        </tr>
      </tbody>
    </table>
    <pre v-else class="diff-raw">{{ pretty }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ changes: Record<string, unknown> }>()

interface DiffRow {
  field: string
  before: unknown
  after: unknown
}

const diffRows = computed<DiffRow[]>(() => {
  const c = props.changes
  if (!c || typeof c !== 'object') return []
  const entries = Object.entries(c)
  if (entries.length === 0) return []
  const isDiffMap = entries.every(([, v]) => v !== null && typeof v === 'object' && 'before' in (v as object) && 'after' in (v as object))
  if (isDiffMap) {
    return entries.map(([field, v]) => {
      const val = v as { before: unknown; after: unknown }
      return { field, before: val.before, after: val.after }
    })
  }
  return []
})

const pretty = computed(() => JSON.stringify(props.changes, null, 2))

function display(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}
</script>

<style scoped>
.diff-panel {
  padding: 14px 16px;
}

.diff-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.diff-table th {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 2px solid var(--line);
  color: var(--text-muted);
  font-weight: 600;
}

.diff-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

.diff-field {
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
}

.diff-old-head { color: var(--danger); }
.diff-new-head { color: #16a34a; }

.diff-old {
  color: var(--danger);
  background: #fef2f2;
  word-break: break-all;
}

.diff-new {
  color: #16a34a;
  background: #f0fdf4;
  word-break: break-all;
}

.diff-raw {
  margin: 0;
  white-space: pre-wrap;
  font-size: 12px;
}
</style>
