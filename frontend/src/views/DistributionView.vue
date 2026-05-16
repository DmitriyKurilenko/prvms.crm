<template>
  <FeatureGate feature="distribution">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Распределение</h1>
      </div>

      <div style="display: flex; gap: 8px; margin-bottom: 12px;">
        <PButton :label="'Правила'" :outlined="activeTab !== 'rules'" @click="activeTab = 'rules'" size="small" />
        <PButton :label="'Лог распределения'" :outlined="activeTab !== 'log'" @click="activeTab = 'log'; loadLog()" size="small" />
      </div>

      <!-- RULES TAB -->
      <template v-if="activeTab === 'rules'">
        <div class="surface-card" style="padding: 16px; margin-bottom: 12px">
          <h3 style="margin: 0 0 12px">{{ editingId ? 'Редактировать правило' : 'Новое правило' }}</h3>
          <form @submit.prevent="submitRule" style="display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end">
              <div style="min-width: 200px;">
                <label class="field-label">Название</label>
                <PInputText v-model="rule.name" placeholder="Название правила" style="width: 100%" />
              </div>
              <div style="min-width: 170px;">
                <label class="field-label">Триггер</label>
                <PSelect v-model="rule.trigger" :options="triggerOptions" optionLabel="label" optionValue="value" style="width: 100%" />
              </div>
              <div style="min-width: 170px;">
                <label class="field-label">Стратегия</label>
                <PSelect v-model="rule.strategy" :options="strategyOptions" optionLabel="label" optionValue="value" style="width: 100%" />
              </div>
              <div style="width: 100px;">
                <label class="field-label">Приоритет</label>
                <PInputText v-model.number="rule.priority" placeholder="0" type="number" style="width: 100%" />
              </div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-start">
              <div style="flex: 1; min-width: 200px;">
                <label class="field-label">Пул менеджеров</label>
                <PMultiSelect v-model="rule.managers" :options="availableManagers" optionLabel="name" optionValue="id"
                  placeholder="Все менеджеры" class="w-full" display="chip" :loading="managersLoading" />
              </div>
              <div style="min-width: 200px;">
                <label class="field-label">Запасной менеджер</label>
                <PSelect v-model="rule.fallback_manager_id" :options="fallbackOptions" optionLabel="name" optionValue="id"
                  placeholder="Не выбран" class="w-full" />
              </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center">
              <PButton type="submit" :label="editingId ? 'Сохранить' : 'Создать'" :icon="editingId ? 'pi pi-check' : 'pi pi-plus'" />
              <PButton v-if="editingId" label="Отмена" text @click="cancelEdit" />
            </div>
          </form>
        </div>

        <div class="surface-card" style="padding: 16px">
          <PDataTable v-responsive-table :value="rules" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
            <PColumn field="name" header="Название" />
            <PColumn header="Триггер">
              <template #body="{ data }">{{ triggerLabel(data.trigger) }}</template>
            </PColumn>
            <PColumn header="Стратегия">
              <template #body="{ data }">{{ strategyLabel(data.strategy) }}</template>
            </PColumn>
            <PColumn header="Менеджеры">
              <template #body="{ data }">
                <span v-if="data.managers?.length">{{ data.managers.length }}</span>
                <span v-else style="color: var(--text-muted)">все</span>
              </template>
            </PColumn>
            <PColumn field="priority" header="Приоритет" />
            <PColumn header="Активно">
              <template #body="{ data }">
                <span :style="{ color: data.is_active ? '#059669' : '#dc2626' }">{{ data.is_active ? 'Да' : 'Нет' }}</span>
              </template>
            </PColumn>
            <PColumn header="">
              <template #body="{ data }">
                <PButton icon="pi pi-pencil" text size="small" @click="startEdit(data)" />
                <PButton icon="pi pi-power-off" text size="small" :severity="data.is_active ? 'warning' : 'success'"
                  @click="toggleActive(data)" :title="data.is_active ? 'Деактивировать' : 'Активировать'" />
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeRule(data.id)" />
              </template>
            </PColumn>
          </PDataTable>
        </div>
      </template>

      <!-- LOG TAB -->
      <template v-if="activeTab === 'log'">
        <div class="surface-card" style="padding: 16px">
          <PDataTable v-responsive-table :value="logEntries" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
            <PColumn header="Дата">
              <template #body="{ data }">{{ formatDateTime(data.created_at) }}</template>
            </PColumn>
            <PColumn field="rule_name" header="Правило" />
            <PColumn header="Сущность">
              <template #body="{ data }">
                {{ data.crm_entity_type === 'deal' ? 'Сделка' : data.crm_entity_type }}
                #{{ data.crm_entity_id }}
                <template v-if="data.entity_name"> — {{ data.entity_name }}</template>
              </template>
            </PColumn>
            <PColumn field="assigned_to_name" header="Назначен" />
            <PColumn header="Источник">
              <template #body="{ data }">{{ sourceLabel(data.source) }}</template>
            </PColumn>
            <PColumn header="Стратегия">
              <template #body="{ data }">{{ strategyLabel(data.strategy_used) }}</template>
            </PColumn>
            <PColumn field="reason" header="Причина" />
          </PDataTable>
          <div v-if="!logEntries.length" style="text-align: center; padding: 32px; color: var(--text-muted);">
            Нет записей в логе распределения
          </div>
        </div>
      </template>
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/http'
import FeatureGate from '@/components/FeatureGate.vue'
import { formatDateTime } from '@/utils/datetime'

const toast = useToast()

interface DistRule {
  id: number
  name: string
  trigger: string
  strategy: string
  priority: number
  is_active: boolean
  managers: number[]
  fallback_manager_id: number | null
}

interface LogEntry {
  id: number
  rule_name: string | null
  crm_entity_type: string
  crm_entity_id: string
  entity_name: string | null
  assigned_to_name: string | null
  source: string
  strategy_used: string
  reason: string
  created_at: string
}

const triggerOptions = [
  { value: 'new_deal', label: 'Новая сделка' },
]
const strategyOptions = [
  { value: 'min_load', label: 'Минимальная нагрузка' },
  { value: 'round_robin', label: 'По очереди' },
  { value: 'weighted', label: 'Взвешенное' },
  { value: 'manual_queue', label: 'Ручная очередь' },
]

const activeTab = ref('rules')
const rules = ref<DistRule[]>([])
const logEntries = ref<LogEntry[]>([])
const availableManagers = ref<Array<{ id: number; name: string }>>([])
const managersLoading = ref(false)
const editingId = ref<number | null>(null)
const rule = reactive({
  name: '',
  trigger: 'new_deal',
  strategy: 'min_load',
  trigger_filter: {} as Record<string, unknown>,
  strategy_config: {} as Record<string, unknown>,
  managers: [] as number[],
  fallback_manager_id: null as number | null,
  is_active: true,
  priority: 0,
})

const fallbackOptions = computed(() => [{ id: null, name: '— не выбран —' }, ...availableManagers.value])

const triggerLabel = (t: string) => ({ new_deal: 'Новая сделка' }[t] || t)
const strategyLabel = (s: string) => ({ min_load: 'Мин. нагрузка', round_robin: 'По очереди', weighted: 'Взвешенное', manual_queue: 'Ручная очередь' }[s] || s)
const sourceLabel = (s: string) => ({ crm_webhook: 'CRM-вебхук', builtin_crm: 'Встроенный CRM', messenger: 'Мессенджер', phone_call: 'Звонок', manual: 'Ручное' }[s] || s)

const load = async () => {
  try {
    rules.value = await api('/distribution/rules/')
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить правила распределения.', life: 5000 })
  }
}

const loadManagers = async () => {
  managersLoading.value = true
  try {
    availableManagers.value = await api('/distribution/managers/')
  } catch { /* empty — no managers configured yet */ }
  managersLoading.value = false
}

const loadLog = async () => {
  try {
    logEntries.value = await api('/distribution/log/')
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить журнал распределения.', life: 5000 })
  }
}

const submitRule = async () => {
  if (!rule.name) return
  const payload = {
    name: rule.name,
    trigger: rule.trigger,
    strategy: rule.strategy,
    priority: rule.priority,
    is_active: rule.is_active,
    managers: rule.managers,
    fallback_manager_id: rule.fallback_manager_id,
    trigger_filter: rule.trigger_filter,
    strategy_config: rule.strategy_config,
  }
  try {
    if (editingId.value) {
      await api(`/distribution/rules/${editingId.value}/`, { method: 'PATCH', body: payload })
      editingId.value = null
    } else {
      await api('/distribution/rules/', { method: 'POST', body: payload })
    }
    resetForm()
    await load()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить правило.', life: 5000 })
  }
}

const startEdit = (r: DistRule) => {
  editingId.value = r.id
  rule.name = r.name
  rule.trigger = r.trigger
  rule.strategy = r.strategy
  rule.priority = r.priority
  rule.is_active = r.is_active
  rule.managers = [...(r.managers || [])]
  rule.fallback_manager_id = r.fallback_manager_id ?? null
}

const cancelEdit = () => {
  editingId.value = null
  resetForm()
}

const resetForm = () => {
  rule.name = ''
  rule.trigger = 'new_deal'
  rule.strategy = 'min_load'
  rule.priority = 0
  rule.is_active = true
  rule.managers = []
  rule.fallback_manager_id = null
  rule.trigger_filter = {}
  rule.strategy_config = {}
}

const toggleActive = async (r: DistRule) => {
  try {
    await api(`/distribution/rules/${r.id}/`, { method: 'PATCH', body: { is_active: !r.is_active } })
    await load()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось изменить статус правила.', life: 5000 })
  }
}

const removeRule = async (id: number) => {
  try {
    await api(`/distribution/rules/${id}/`, { method: 'DELETE' })
    await load()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить правило.', life: 5000 })
  }
}

onMounted(() => {
  load()
  loadManagers()
})
</script>

<style scoped>
.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
</style>
