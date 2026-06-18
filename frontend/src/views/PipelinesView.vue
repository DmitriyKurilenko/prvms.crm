<template>
  <FeatureGate feature="crm_builtin">
    <section class="pipelines-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Воронки и триггеры</h1>
      </div>

      <div v-if="!canManage" class="surface-card" style="padding: 14px;">
        Управление воронками доступно только владельцу или администратору.
      </div>

      <template v-else>
        <div class="tabs-bar">
          <button :class="['tab-btn', { active: tab === 'pipelines' }]" @click="tab = 'pipelines'">Воронки</button>
          <button :class="['tab-btn', { active: tab === 'triggers' }]" @click="tab = 'triggers'">Триггеры</button>
        </div>

        <div v-if="tab === 'pipelines'" class="tab-content">
          <div class="toolbar">
            <PButton label="Новая воронка" icon="pi pi-plus" size="small" @click="openCreatePipeline" />
          </div>
          <div v-for="p in pipelines" :key="p.id" class="surface-card pipeline-card">
            <div class="pipeline-header">
              <strong>{{ p.name }}</strong>
              <div>
                <PButton icon="pi pi-cog" text size="small" @click="togglePipelineStages(p)" :title="selectedPipelineFor === p.id ? 'Свернуть' : 'Этапы'" />
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removePipeline(p.id)" />
              </div>
            </div>
            <div v-if="selectedPipelineFor === p.id && selectedStages" class="pipeline-stages">
              <div
                v-for="(s, idx) in selectedStages"
                :key="s.id"
                class="stage-row-draggable"
                draggable="true"
                @dragstart="onStageDragStart($event, idx)"
                @dragover.prevent
                @drop="onStageDrop($event, idx, p.id)"
              >
                <span class="stage-drag-handle">⠿</span>
                <span class="stage-dot" :style="{ background: s.color }" />
                <span class="stage-name-text">{{ s.name }}</span>
                <PTag :value="stageTypeLabel(s.stage_type)" :severity="stageTypeSeverity(s.stage_type)" class="stage-type-tag" />
                <PTag v-if="triggerLabel(s)" :value="triggerLabel(s)" severity="warn" />
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeStage(s.id, p.id)" />
              </div>
              <div class="add-stage-row">
                <PInputText v-model="newStageName" placeholder="Новая стадия" />
                <PButton label="Добавить" size="small" @click="addStage(p.id)" :disabled="!newStageName" />
              </div>
            </div>
          </div>
          <div v-if="!pipelines.length" class="empty-state">Нет воронок</div>
        </div>

        <div v-if="tab === 'triggers'" class="tab-content">
          <div class="toolbar">
            <PButton label="Новый триггер" icon="pi pi-plus" size="small" @click="openNewTrigger" />
          </div>
          <PDataTable v-responsive-table :value="allTriggers" size="small" stripedRows :paginator="allTriggers.length > 20" :rows="20">
            <PColumn field="pipeline_name" header="Воронка" />
            <PColumn header="Этап">
              <template #body="{ data }">
                <span class="stage-dot" :style="{ background: data.stage_color }" />
                {{ data.stage_name }}
              </template>
            </PColumn>
            <PColumn field="action_label" header="Действие" />
            <PColumn header="Параметры">
              <template #body="{ data }">
                <span v-if="data.action_type === 'create_task'">{{ data.action_title }} (через {{ data.action_days_offset }} дн.)</span>
                <span v-else-if="data.action_type === 'send_notification'">Событие: {{ data.action_event }}</span>
                <span v-else>—</span>
              </template>
            </PColumn>
            <PColumn header="" style="width: 100px">
              <template #body="{ data }">
                <PButton icon="pi pi-pencil" text size="small" @click="editTrigger(data)" />
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="deleteTrigger(data)" />
              </template>
            </PColumn>
          </PDataTable>
          <div v-if="!allTriggers.length" class="empty-state">Нет настроенных триггеров</div>
        </div>
      </template>

      <PDialog v-model:visible="showPipelineForm" header="Новая воронка" :style="{ width: '400px' }" modal>
        <div class="form-grid">
          <PInputText v-model="pipelineForm.name" placeholder="Название воронки" />
          <PButton label="Создать" :disabled="!pipelineForm.name" @click="submitPipeline" />
        </div>
      </PDialog>

      <PDialog v-model:visible="showTriggerConfig" header="Триггер" :style="{ width: '450px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div v-if="!triggerStage">
            <label class="field-label">Воронка *</label>
            <PSelect v-model="triggerPipelineId" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Выберите воронку" @change="onTriggerPipelineChange" class="w-full" />
          </div>
          <div v-if="!triggerStage">
            <label class="field-label">Этап *</label>
            <PSelect v-model="triggerStageId" :options="triggerStageOptions" optionLabel="label" optionValue="value" placeholder="Выберите этап" class="w-full" />
          </div>
          <div v-if="triggerStage">
            <label class="field-label">Этап: {{ triggerStage.name }}</label>
          </div>
          <div>
            <label class="field-label">Действие *</label>
            <PSelect v-model="triggerForm.type" :options="triggerTypeOptions" optionLabel="label" optionValue="value" placeholder="Выберите действие" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'create_task'">
            <label class="field-label">Название задачи</label>
            <PInputText v-model="triggerForm.title" placeholder="Новая задача" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'create_task'">
            <label class="field-label">Через дней</label>
            <PInputText v-model.number="triggerForm.days_offset" type="number" min="0" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'send_notification'">
            <label class="field-label">Событие</label>
            <PInputText v-model="triggerForm.event" placeholder="deal_stage_changed" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'create_document'">
            <label class="field-label">Шаблон документа *</label>
            <PSelect v-model="triggerForm.template_id" :options="triggerTemplateOptions" optionLabel="label" optionValue="value" placeholder="Выберите шаблон" class="w-full" />
          </div>
          <PButton
            label="Сохранить"
            :disabled="!triggerForm.type || (!triggerStage && !triggerStageId) || (triggerForm.type === 'create_document' && !triggerForm.template_id)"
            @click="saveTrigger"
          />
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
import type { CrmPipeline, CrmStage } from '@/api/crm'
import { api } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'

const log = createLogger('pipelines')
const toast = useToast()
const authStore = useAuthStore()

const canManage = computed(() => ['owner', 'admin'].includes(authStore.role || ''))

const tab = ref<'pipelines' | 'triggers'>('pipelines')
const pipelines = ref<CrmPipeline[]>([])
const showPipelineForm = ref(false)
const pipelineForm = reactive({ name: '' })

const selectedStages = ref<CrmStage[] | null>(null)
const selectedPipelineFor = ref<number | null>(null)
const newStageName = ref('')
let dragStageIdx: number | null = null

const showTriggerConfig = ref(false)
const triggerStage = ref<CrmStage | null>(null)
const triggerPipelineId = ref<number | null>(null)
const triggerStageId = ref<number | null>(null)
const triggerStagesList = ref<CrmStage[]>([])
const triggerForm = reactive({
  type: '' as string,
  title: '',
  days_offset: 1,
  event: 'deal_stage_changed',
  template_id: null as number | null,
})
const triggerTypeOptions = [
  { label: 'Создать задачу', value: 'create_task' },
  { label: 'Отправить уведомление', value: 'send_notification' },
  { label: 'Создать документ', value: 'create_document' },
]
const documentTemplates = ref<Array<{ id: number; name: string }>>([])
const triggerTemplateOptions = computed(() => documentTemplates.value.map(t => ({ label: t.name, value: t.id })))
const triggerStageOptions = computed(() => triggerStagesList.value.map(s => ({ label: s.name, value: s.id })))
const allPipelineStages = ref<Map<number, CrmStage[]>>(new Map())

async function loadDocumentTemplates() {
  if (documentTemplates.value.length) return
  try {
    documentTemplates.value = await api<Array<{ id: number; name: string }>>('/documents/templates/')
  } catch {
    // Templates are optional — silent failure preserves UI.
  }
}

async function loadPipelines() {
  if (!canManage.value) {
    pipelines.value = []
    return
  }
  try {
    pipelines.value = await crmApi.listPipelines()
  } catch (err) {
    log.error('Failed to load pipelines', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить воронки', life: 5000 })
  }
}

async function loadAllTriggers() {
  if (!canManage.value) {
    allPipelineStages.value = new Map()
    return
  }
  await loadDocumentTemplates()
  const map = new Map<number, CrmStage[]>()
  for (const p of pipelines.value) {
    try {
      map.set(p.id, await crmApi.listStages(p.id))
    } catch {
      map.set(p.id, [])
    }
  }
  allPipelineStages.value = map
}

const allTriggers = computed(() => {
  const result: Array<{
    pipeline_id: number; pipeline_name: string; stage_id: number; stage_name: string
    stage_color: string; action_type: string; action_label: string
    action_title: string; action_days_offset: number; action_event: string
    action_template_id: number | null; stage: CrmStage
  }> = []
  for (const p of pipelines.value) {
    const stages = allPipelineStages.value.get(p.id) || []
    for (const s of stages) {
      const a = s.auto_action as Record<string, unknown> | undefined
      if (a && a.type) {
        const opt = triggerTypeOptions.find(o => o.value === a.type)
        let label = opt?.label || String(a.type)
        const templateId = (a.template_id as number) || null
        if (a.type === 'create_document' && templateId) {
          const tpl = documentTemplates.value.find(t => t.id === templateId)
          if (tpl) label += ` (${tpl.name})`
        }
        result.push({
          pipeline_id: p.id, pipeline_name: p.name,
          stage_id: s.id, stage_name: s.name, stage_color: s.color,
          action_type: a.type as string, action_label: label,
          action_title: (a.title as string) || '', action_days_offset: (a.days_offset as number) || 0,
          action_event: (a.event as string) || '', action_template_id: templateId, stage: s,
        })
      }
    }
  }
  return result
})

function stageTypeLabel(t: string) {
  const map: Record<string, string> = { open: 'В работе', won: 'Успешно', lost: 'Проиграна' }
  return map[t] || t
}

function stageTypeSeverity(t: string) {
  const map: Record<string, string> = { open: 'info', won: 'success', lost: 'danger' }
  return (map[t] || 'secondary') as 'info' | 'success' | 'danger' | 'secondary'
}

function triggerLabel(s: CrmStage): string {
  const action = s.auto_action || {}
  const t = (action as Record<string, unknown>).type as string | undefined
  if (!t) return ''
  const map: Record<string, string> = { create_task: '📋 Задача', send_notification: '🔔 Уведомление', create_document: '📄 Документ' }
  return map[t] || t
}

async function togglePipelineStages(p: CrmPipeline) {
  if (selectedPipelineFor.value === p.id) {
    selectedPipelineFor.value = null
    selectedStages.value = null
    return
  }
  try {
    selectedStages.value = await crmApi.listStages(p.id)
    selectedPipelineFor.value = p.id
  } catch (err) {
    log.error('Failed to load stages', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить этапы', life: 5000 })
  }
}

async function addStage(pipelineId: number) {
  if (!newStageName.value) return
  try {
    await crmApi.createStage(pipelineId, { name: newStageName.value })
    newStageName.value = ''
    selectedStages.value = await crmApi.listStages(pipelineId)
  } catch (err) {
    log.error('Failed to add stage', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось добавить этап', life: 5000 })
  }
}

async function removeStage(stageId: number, pipelineId: number) {
  try {
    await crmApi.deleteStage(stageId)
    selectedStages.value = await crmApi.listStages(pipelineId)
  } catch (err) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail || 'Невозможно удалить этап (есть сделки)'
    toast.add({ severity: 'error', summary: 'Ошибка', detail, life: 5000 })
  }
}

function onStageDragStart(e: DragEvent, idx: number) {
  dragStageIdx = idx
  e.dataTransfer?.setData('text/plain', String(idx))
}

async function onStageDrop(_e: DragEvent, targetIdx: number, pipelineId: number) {
  if (dragStageIdx === null || dragStageIdx === targetIdx || !selectedStages.value) return
  const arr = [...selectedStages.value]
  const [moved] = arr.splice(dragStageIdx, 1)
  arr.splice(targetIdx, 0, moved)
  selectedStages.value = arr
  dragStageIdx = null
  try {
    await crmApi.reorderStages(pipelineId, arr.map(s => s.id))
  } catch (err) {
    log.error('Failed to reorder stages', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось переупорядочить этапы', life: 5000 })
  }
}

function openCreatePipeline() {
  pipelineForm.name = ''
  showPipelineForm.value = true
}

async function submitPipeline() {
  if (!pipelineForm.name) return
  try {
    await crmApi.createPipeline({ name: pipelineForm.name })
    showPipelineForm.value = false
    pipelineForm.name = ''
    await loadPipelines()
  } catch (err) {
    log.error('Failed to create pipeline', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать воронку', life: 5000 })
  }
}

async function removePipeline(id: number) {
  try {
    await crmApi.deletePipeline(id)
    if (selectedPipelineFor.value === id) {
      selectedPipelineFor.value = null
      selectedStages.value = null
    }
    await loadPipelines()
  } catch (err) {
    log.error('Failed to delete pipeline', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить воронку', life: 5000 })
  }
}

async function onTriggerPipelineChange() {
  triggerStageId.value = null
  if (triggerPipelineId.value) {
    try {
      triggerStagesList.value = await crmApi.listStages(triggerPipelineId.value)
    } catch {
      triggerStagesList.value = []
    }
  } else {
    triggerStagesList.value = []
  }
}

function openNewTrigger() {
  triggerStage.value = null
  triggerPipelineId.value = null
  triggerStageId.value = null
  triggerStagesList.value = []
  Object.assign(triggerForm, { type: '', title: 'Новая задача', days_offset: 1, event: 'deal_stage_changed', template_id: null })
  loadDocumentTemplates()
  showTriggerConfig.value = true
}

function editTrigger(row: { stage: CrmStage }) {
  const s = row.stage
  triggerStage.value = s
  triggerPipelineId.value = null
  triggerStageId.value = null
  const action = (s.auto_action || {}) as Record<string, unknown>
  triggerForm.type = (action.type as string) || ''
  triggerForm.title = (action.title as string) || 'Новая задача'
  triggerForm.days_offset = (action.days_offset as number) ?? 1
  triggerForm.event = (action.event as string) || 'deal_stage_changed'
  triggerForm.template_id = (action.template_id as number) ?? null
  loadDocumentTemplates()
  showTriggerConfig.value = true
}

async function deleteTrigger(row: { stage_id: number }) {
  try {
    await crmApi.patchStage(row.stage_id, { auto_action: {} })
    await loadAllTriggers()
  } catch (err) {
    log.error('Failed to delete trigger', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить триггер', life: 5000 })
  }
}

async function saveTrigger() {
  const stageId = triggerStage.value?.id || triggerStageId.value
  if (!stageId || !triggerForm.type) return
  const auto_action: Record<string, unknown> = { type: triggerForm.type }
  if (triggerForm.type === 'create_task') {
    auto_action.title = triggerForm.title
    auto_action.days_offset = triggerForm.days_offset
  } else if (triggerForm.type === 'send_notification') {
    auto_action.event = triggerForm.event
  } else if (triggerForm.type === 'create_document') {
    if (!triggerForm.template_id) return
    auto_action.template_id = triggerForm.template_id
  }
  try {
    await crmApi.patchStage(stageId, { auto_action })
    showTriggerConfig.value = false
    await loadAllTriggers()
    if (selectedPipelineFor.value) {
      selectedStages.value = await crmApi.listStages(selectedPipelineFor.value)
    }
  } catch (err) {
    log.error('Failed to save trigger', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить триггер', life: 5000 })
  }
}

onMounted(async () => {
  await loadPipelines()
  await loadAllTriggers()
})
</script>

<style scoped>
.pipelines-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.tabs-bar { display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap; overflow-x: auto; }
.tab-btn {
  background: transparent; border: 1px solid var(--p-content-border-color);
  padding: 6px 14px; border-radius: 6px; cursor: pointer; color: var(--p-text-color);
  font-size: 13.5px;
}
.tab-btn.active { background: var(--p-primary-50); color: var(--p-primary-color); border-color: var(--p-primary-color); }
.tab-content { padding-top: 4px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.pipeline-card { padding: 14px; margin-bottom: 10px; }
.pipeline-header { display: flex; justify-content: space-between; align-items: center; }
.pipeline-stages { margin-top: 10px; }
.stage-row-draggable {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border: 1px dashed transparent; border-radius: 4px;
}
.stage-row-draggable:hover { border-color: var(--p-content-border-color); background: var(--p-surface-hover); }
.stage-drag-handle { cursor: grab; color: var(--p-text-muted-color); }
.stage-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.stage-name-text { flex: 1; font-weight: 500; }
.stage-type-tag { font-size: 11px; }
.add-stage-row { display: flex; gap: 8px; margin-top: 8px; }
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.field-label { display: block; font-size: 12px; color: var(--p-text-muted-color); margin-bottom: 4px; font-weight: 600; }
.empty-state { padding: 20px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
.w-full { width: 100%; }
</style>
