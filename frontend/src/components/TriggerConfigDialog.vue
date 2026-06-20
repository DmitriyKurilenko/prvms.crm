<template>
  <PDialog :visible="visible" @update:visible="$emit('update:visible', $event)" header="Триггер" :style="{ width: '450px', maxWidth: '95vw' }" modal>
    <div class="form-grid">
      <div v-if="!triggerStage">
        <label class="field-label">Воронка *</label>
        <PSelect
          :modelValue="pipelineId"
          @update:modelValue="$emit('update:pipelineId', $event)"
          @change="$emit('pipelineChange')"
          :options="pipelines"
          optionLabel="name"
          optionValue="id"
          placeholder="Выберите воронку"
          class="w-full"
        />
      </div>
      <div v-if="!triggerStage">
        <label class="field-label">Этап *</label>
        <PSelect
          :modelValue="stageId"
          @update:modelValue="$emit('update:stageId', $event)"
          :options="stageOptions"
          optionLabel="label"
          optionValue="value"
          placeholder="Выберите этап"
          class="w-full"
        />
      </div>
      <div v-if="triggerStage">
        <label class="field-label">Этап: {{ triggerStage.name }}</label>
      </div>
      <div>
        <label class="field-label">Действие *</label>
        <PSelect v-model="form.type" :options="typeOptions" optionLabel="label" optionValue="value" placeholder="Выберите действие" class="w-full" />
      </div>
      <div v-if="form.type === 'create_task'">
        <label class="field-label">Название задачи</label>
        <PInputText v-model="form.title" placeholder="Новая задача" class="w-full" />
      </div>
      <div v-if="form.type === 'create_task'">
        <label class="field-label">Через дней</label>
        <PInputText v-model.number="form.days_offset" type="number" min="0" class="w-full" />
      </div>
      <div v-if="form.type === 'send_notification'">
        <label class="field-label">Событие</label>
        <PInputText v-model="form.event" placeholder="deal_stage_changed" class="w-full" />
      </div>
      <div v-if="form.type === 'create_document'">
        <label class="field-label">Шаблон документа *</label>
        <PSelect v-model="form.template_id" :options="templateOptions" optionLabel="label" optionValue="value" placeholder="Выберите шаблон" class="w-full" />
      </div>
      <PButton
        label="Сохранить"
        :disabled="!form.type || (!triggerStage && !stageId) || (form.type === 'create_document' && !form.template_id)"
        @click="$emit('save')"
      />
    </div>
  </PDialog>
</template>

<script setup lang="ts">
import type { CrmPipeline, CrmStage } from '@/api/crm'

/**
 * Презентационный диалог настройки триггера этапа. Реактивная form и логика
 * сохранения/загрузки остаются в родителе (PipelinesView). Выбор воронки/этапа
 * проброшен через update-события (отдельные ref в родителе). Перенос 1:1.
 */
interface TriggerForm {
  type: string
  title: string
  days_offset: number
  event: string
  template_id: number | null
}

defineProps<{
  visible: boolean
  triggerStage: CrmStage | null
  pipelines: CrmPipeline[]
  stageOptions: { value: number; label: string }[]
  form: TriggerForm
  typeOptions: { value: string; label: string }[]
  templateOptions: { value: number; label: string }[]
  pipelineId: number | null
  stageId: number | null
}>()

defineEmits<{
  'update:visible': [boolean]
  'update:pipelineId': [number | null]
  'update:stageId': [number | null]
  pipelineChange: []
  save: []
}>()
</script>

<style scoped>
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.field-label { display: block; font-size: 12px; color: var(--p-text-muted-color); margin-bottom: 4px; font-weight: 600; }
.w-full { width: 100%; }
</style>
