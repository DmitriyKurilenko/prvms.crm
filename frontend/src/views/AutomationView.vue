<template>
  <FeatureGate feature="crm_builtin">
    <section class="automation-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Автоматизации</h1>
      </div>

      <div v-if="!canManage" class="surface-card" style="padding: 14px;">
        Управление автоматизациями доступно владельцу и администратору.
      </div>

      <template v-else>
        <div class="toolbar">
          <PButton label="Новое правило" icon="pi pi-plus" size="small" @click="openCreate" />
        </div>

        <div class="surface-card" style="padding: 12px; margin-top: 12px;">
          <PDataTable v-responsive-table :value="rules" size="small" stripedRows :paginator="true" :rows="20">
            <PColumn field="name" header="Название" />
            <PColumn header="Триггер">
              <template #body="{ data }">{{ triggerLabel(data.trigger) }}</template>
            </PColumn>
            <PColumn header="Действие">
              <template #body="{ data }">{{ actionLabel(data.action?.type) }}</template>
            </PColumn>
            <PColumn header="Активно">
              <template #body="{ data }">
                <PTag :value="data.is_active ? 'Да' : 'Нет'" :severity="data.is_active ? 'success' : 'secondary'" />
              </template>
            </PColumn>
            <PColumn header="" style="width: 70px">
              <template #body="{ data }">
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="remove(data.id)" />
              </template>
            </PColumn>
            <template #empty>
              <div class="empty-state">Правил пока нет</div>
            </template>
          </PDataTable>
        </div>
      </template>

      <PDialog v-model:visible="dialogVisible" header="Новое правило" :style="{ width: '520px' }" modal>
        <div class="form-grid">
          <PInputText v-model="form.name" placeholder="Название правила" />
          <div>
            <label class="field-label">Триггер (если...)</label>
            <PSelect v-model="form.trigger" :options="triggerOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
          <div v-if="form.trigger === 'no_activity'">
            <label class="field-label">Дней без активности</label>
            <PInputNumber v-model="form.days" :min="1" :max="365" class="w-full" />
          </div>
          <div>
            <label class="field-label">Действие (то...)</label>
            <PSelect v-model="form.actionType" :options="actionOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
          <div v-if="form.actionType === 'create_task'">
            <label class="field-label">Текст задачи</label>
            <PInputText v-model="form.taskTitle" placeholder="Например, «Перезвонить клиенту»" class="w-full" />
          </div>
          <PButton label="Создать" :disabled="!form.name || !form.trigger || !form.actionType" @click="submit" />
        </div>
      </PDialog>
    </section>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmAutomationRule } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'

const log = createLogger('automation')
const toast = useToast()
const authStore = useAuthStore()
const canManage = computed(() => ['owner', 'admin'].includes(authStore.user?.role || ''))

const triggerOptions = [
  { value: 'new_deal', label: 'Создана сделка' },
  { value: 'stage_changed', label: 'Смена стадии' },
  { value: 'no_activity', label: 'Нет активности N дней' },
]
const actionOptions = [
  { value: 'create_task', label: 'Создать задачу' },
  { value: 'send_notification', label: 'Отправить уведомление' },
]
const triggerLabel = (v: string) => triggerOptions.find(o => o.value === v)?.label ?? v
const actionLabel = (v?: string) => actionOptions.find(o => o.value === v)?.label ?? (v ?? '—')

const rules = ref<CrmAutomationRule[]>([])
const dialogVisible = ref(false)
const form = reactive({
  name: '',
  trigger: 'new_deal',
  days: 3,
  actionType: 'create_task',
  taskTitle: '',
})

async function load() {
  if (!canManage.value) { rules.value = []; return }
  try {
    rules.value = await crmApi.listAutomationRules()
  } catch (err) {
    log.error('Failed to load automation rules', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить правила', life: 5000 })
  }
}

function openCreate() {
  form.name = ''
  form.trigger = 'new_deal'
  form.days = 3
  form.actionType = 'create_task'
  form.taskTitle = ''
  dialogVisible.value = true
}

async function submit() {
  if (!form.name || !form.trigger || !form.actionType) return
  const conditions: Record<string, unknown> = {}
  if (form.trigger === 'no_activity') conditions.days = form.days
  const action: Record<string, unknown> = { type: form.actionType }
  if (form.actionType === 'create_task') action.title = form.taskTitle || 'Новая задача'
  if (form.actionType === 'send_notification') action.event = 'deal_stage_changed'
  try {
    await crmApi.createAutomationRule({ name: form.name, trigger: form.trigger, conditions, action })
    dialogVisible.value = false
    await load()
  } catch (err) {
    log.error('Failed to create rule', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать правило', life: 5000 })
  }
}

async function remove(id: number) {
  try {
    await crmApi.deleteAutomationRule(id)
    await load()
  } catch (err) {
    log.error('Failed to delete rule', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить правило', life: 5000 })
  }
}

onMounted(load)
</script>

<style scoped>
.automation-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { display: flex; gap: 8px; align-items: center; }
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
.empty-state { padding: 18px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
