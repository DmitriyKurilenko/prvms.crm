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
              <template #body="{ data }">{{ actionSummary(data.action) }}</template>
            </PColumn>
            <PColumn header="Условия">
              <template #body="{ data }">{{ conditionsSummary(data.conditions) }}</template>
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

      <PDialog v-model:visible="dialogVisible" header="Новое правило" :style="{ width: '540px' }" modal>
        <div class="form-grid">
          <div>
            <label class="field-label">Название</label>
            <PInputText v-model="form.name" placeholder="Название правила" class="w-full" />
          </div>

          <div>
            <label class="field-label">Триггер (если...)</label>
            <PSelect v-model="form.trigger" :options="triggerOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
          <div v-if="form.trigger === 'no_activity' || form.trigger === 'sla_breach'">
            <label class="field-label">{{ form.trigger === 'sla_breach' ? 'Дней на стадии (SLA)' : 'Дней без активности' }}</label>
            <PInputNumber v-model="form.days" :min="1" :max="365" class="w-full" />
            <small v-if="form.trigger === 'sla_breach'" class="hint">Укажите стадию в условиях ниже — правило сработает, если сделка висит на ней дольше указанного срока.</small>
          </div>

          <PDivider />
          <div class="section-hint">Условия (необязательно): правило сработает только для выбранной воронки/стадии.</div>
          <div>
            <label class="field-label">Воронка</label>
            <PSelect v-model="form.condPipelineId" :options="pipelineOptions" optionLabel="label" optionValue="value" placeholder="Любая воронка" showClear class="w-full" @change="onPipelineChange" />
          </div>
          <div v-if="form.condPipelineId">
            <label class="field-label">Стадия</label>
            <PSelect v-model="form.condStageId" :options="stageOptions" optionLabel="label" optionValue="value" placeholder="Любая стадия" showClear class="w-full" />
          </div>

          <PDivider />
          <div>
            <label class="field-label">Действие (то...)</label>
            <PSelect v-model="form.actionType" :options="actionOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>

          <div v-if="form.actionType === 'create_task'">
            <label class="field-label">Текст задачи</label>
            <PInputText v-model="form.taskTitle" placeholder="Например, «Перезвонить клиенту»" class="w-full" />
          </div>

          <div v-if="form.actionType === 'change_stage'">
            <label class="field-label">Целевая стадия</label>
            <PSelect v-if="form.condPipelineId" v-model="form.targetStageId" :options="stageOptions" optionLabel="label" optionValue="value" placeholder="Выберите стадию" class="w-full" />
            <small v-else class="hint">Сначала выберите воронку в условиях — стадия берётся из неё.</small>
          </div>

          <div v-if="form.actionType === 'assign'">
            <label class="field-label">Ответственный</label>
            <PSelect v-model="form.assignManagerId" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="Выберите менеджера" filter class="w-full" />
          </div>

          <div v-if="form.actionType === 'create_document'">
            <label class="field-label">Шаблон документа</label>
            <PSelect v-model="form.templateId" :options="templateOptions" optionLabel="label" optionValue="value" placeholder="Выберите шаблон" class="w-full" />
            <small v-if="!templateOptions.length" class="hint">Нет доступных шаблонов документов.</small>
          </div>

          <PButton label="Создать" :disabled="!canSubmit" @click="submit" />
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
import { api } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { createLogger } from '@/utils/logger'

const log = createLogger('automation')
const toast = useToast()
const authStore = useAuthStore()
const tenant = useTenantStore()
const canManage = computed(() => ['owner', 'admin'].includes(authStore.user?.role || ''))
const hasDocuments = computed(() => tenant.hasFeature('documents'))

const triggerOptions = [
  { value: 'new_deal', label: 'Создана сделка' },
  { value: 'stage_changed', label: 'Смена стадии' },
  { value: 'no_activity', label: 'Нет активности N дней' },
  { value: 'sla_breach', label: 'Просрочка SLA на стадии' },
]
const baseActionOptions = [
  { value: 'create_task', label: 'Создать задачу' },
  { value: 'send_notification', label: 'Отправить уведомление' },
  { value: 'change_stage', label: 'Сменить стадию' },
  { value: 'assign', label: 'Назначить ответственного' },
  { value: 'create_document', label: 'Создать документ' },
]
const actionOptions = computed(() =>
  baseActionOptions.filter(o => o.value !== 'create_document' || hasDocuments.value),
)
const triggerLabel = (v: string) => triggerOptions.find(o => o.value === v)?.label ?? v
const actionLabel = (v?: string) => baseActionOptions.find(o => o.value === v)?.label ?? (v ?? '—')

/* --- Data --- */
const rules = ref<CrmAutomationRule[]>([])
const pipelines = ref<crmApi.CrmPipeline[]>([])
const stages = ref<crmApi.CrmStage[]>([])
const managers = ref<{ id: number; name: string }[]>([])
const templates = ref<{ id: number; name: string }[]>([])

const pipelineOptions = computed(() => pipelines.value.map(p => ({ label: p.name, value: p.id })))
const stageOptions = computed(() => stages.value.map(s => ({ label: s.name, value: s.id })))
const managerOptions = computed(() => managers.value.map(m => ({ label: m.name, value: m.id })))
const templateOptions = computed(() => templates.value.map(t => ({ label: t.name, value: t.id })))

const pipelineName = (id?: number) => pipelines.value.find(p => p.id === id)?.name
const stageName = (id?: number) => stages.value.find(s => s.id === id)?.name
const managerName = (id?: number) => managers.value.find(m => m.id === id)?.name
const templateName = (id?: number) => templates.value.find(t => t.id === id)?.name

const actionSummary = (action?: Record<string, unknown>) => {
  if (!action?.type) return '—'
  const label = actionLabel(action.type as string)
  if (action.type === 'change_stage') return `${label}: ${stageName(action.stage_id as number) ?? '#' + action.stage_id}`
  if (action.type === 'assign') return `${label}: ${managerName(action.responsible_id as number) ?? '#' + action.responsible_id}`
  if (action.type === 'create_document') return `${label}: ${templateName(action.template_id as number) ?? '#' + action.template_id}`
  if (action.type === 'create_task') return `${label}: ${action.title ?? ''}`
  return label
}
const conditionsSummary = (conditions?: Record<string, unknown>) => {
  if (!conditions) return '—'
  const parts: string[] = []
  if (conditions.pipeline_id) parts.push(`воронка: ${pipelineName(conditions.pipeline_id as number) ?? '#' + conditions.pipeline_id}`)
  if (conditions.stage_id) parts.push(`стадия: ${stageName(conditions.stage_id as number) ?? '#' + conditions.stage_id}`)
  if (conditions.days) parts.push(`${conditions.days} дн.`)
  return parts.length ? parts.join(', ') : '—'
}

const dialogVisible = ref(false)
const form = reactive({
  name: '',
  trigger: 'new_deal',
  days: 3,
  condPipelineId: null as number | null,
  condStageId: null as number | null,
  actionType: 'create_task',
  taskTitle: '',
  targetStageId: null as number | null,
  assignManagerId: null as number | null,
  templateId: null as number | null,
})

const canSubmit = computed(() => {
  if (!form.name || !form.trigger || !form.actionType) return false
  if (form.actionType === 'change_stage') return !!form.condPipelineId && !!form.targetStageId
  if (form.actionType === 'assign') return !!form.assignManagerId
  if (form.actionType === 'create_document') return !!form.templateId
  return true
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

async function onPipelineChange() {
  form.condStageId = null
  form.targetStageId = null
  stages.value = []
  if (form.condPipelineId) {
    try {
      stages.value = await crmApi.listStages(form.condPipelineId)
    } catch (err) {
      log.error('Failed to load stages', err)
    }
  }
}

function openCreate() {
  Object.assign(form, {
    name: '', trigger: 'new_deal', days: 3,
    condPipelineId: null, condStageId: null,
    actionType: 'create_task', taskTitle: '',
    targetStageId: null, assignManagerId: null, templateId: null,
  })
  stages.value = []
  dialogVisible.value = true
}

async function submit() {
  if (!canSubmit.value) return
  const conditions: Record<string, unknown> = {}
  if (form.trigger === 'no_activity' || form.trigger === 'sla_breach') conditions.days = form.days
  if (form.condPipelineId) conditions.pipeline_id = form.condPipelineId
  if (form.condStageId) conditions.stage_id = form.condStageId

  const action: Record<string, unknown> = { type: form.actionType }
  if (form.actionType === 'create_task') action.title = form.taskTitle || 'Новая задача'
  if (form.actionType === 'send_notification') action.event = 'deal_stage_changed'
  if (form.actionType === 'change_stage') action.stage_id = form.targetStageId
  if (form.actionType === 'assign') action.responsible_id = form.assignManagerId
  if (form.actionType === 'create_document') action.template_id = form.templateId

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

onMounted(async () => {
  await Promise.all([
    load(),
    crmApi.listPipelines().then(r => (pipelines.value = r)).catch(() => { /* опционально */ }),
    crmApi.listManagers().then(r => (managers.value = r)).catch(() => { /* опционально */ }),
    hasDocuments.value
      ? api<{ id: number; name: string }[]>('/documents/templates/').then(r => (templates.value = r)).catch(() => { /* нет доступа к шаблонам */ })
      : Promise.resolve(),
  ])
})
</script>

<style scoped>
.automation-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { display: flex; gap: 8px; align-items: center; }
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.section-hint { font-size: 12px; color: var(--p-text-muted-color); }
.hint { display: block; font-size: 12px; color: var(--p-text-muted-color); margin-top: 4px; }
.w-full { width: 100%; }
.empty-state { padding: 18px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
