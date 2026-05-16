<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    header="Новая сделка"
    :style="{ width: '500px', maxWidth: '95vw' }"
    modal
  >
    <div class="form-grid">
      <div>
        <label class="field-label">Название *</label>
        <PInputText v-model="form.name" placeholder="Название сделки" class="w-full" />
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Воронка *</label>
          <PSelect v-model="form.pipeline_id" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Воронка" @change="$emit('pipelineChange')" class="w-full" />
        </div>
        <div>
          <label class="field-label">Стадия</label>
          <PSelect v-model="form.stage_id" :options="stageOptions" optionLabel="label" optionValue="value" placeholder="Первая стадия" class="w-full" />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Сумма</label>
          <PInputText v-model.number="form.amount" placeholder="0" type="number" class="w-full" />
        </div>
        <div>
          <label class="field-label">Валюта</label>
          <PSelect v-model="form.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Контакт</label>
          <div class="select-with-add">
            <PSelect v-model="form.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
            <PButton v-if="canCreateContact" icon="pi pi-plus" size="small" outlined @click="$emit('quickContact')" />
          </div>
        </div>
        <div>
          <label class="field-label">Компания</label>
          <div class="select-with-add">
            <PSelect v-model="form.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
            <PButton v-if="canCreateCompany" icon="pi pi-plus" size="small" outlined @click="$emit('quickCompany')" />
          </div>
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Ответственный</label>
          <PSelect v-model="form.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" />
        </div>
        <div>
          <label class="field-label">Дата закрытия</label>
          <PInputText v-model="form.expected_close_date" type="date" class="w-full" />
        </div>
      </div>
      <div>
        <label class="field-label">Источник</label>
        <PSelect v-model="form.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" />
      </div>
      <PButton label="Создать" :disabled="!form.name || !form.pipeline_id" @click="$emit('submit')" />
    </div>
  </PDialog>
</template>

<script setup lang="ts">
import type { CrmPipeline } from '@/api/crm'

/**
 * Presentational shell. `form` is the parent's reactive object passed by
 * reference — v-model here mutates the same proxy the parent owns, so
 * `submitDeal`/`onDealPipelineChange` (kept in the parent) see field
 * changes without state migration. Actions bubble via emits.
 */
export interface DealFormModel {
  name: string
  pipeline_id: number | null
  stage_id: number | null
  amount: number | null
  currency: string
  contact_id: number | null
  company_id: number | null
  responsible_id: number | null
  expected_close_date: string
  source: string
}
type NumOption = { label: string; value: number }
type StrOption = { label: string; value: string }

defineProps<{
  visible: boolean
  form: DealFormModel
  pipelines: CrmPipeline[]
  stageOptions: NumOption[]
  contactOptions: NumOption[]
  companyOptions: NumOption[]
  managerOptions: NumOption[]
  sourceOptions: StrOption[]
  currencies: StrOption[]
  canCreateContact: boolean
  canCreateCompany: boolean
}>()

defineEmits<{
  'update:visible': [boolean]
  submit: []
  pipelineChange: []
  quickContact: []
  quickCompany: []
}>()
</script>

<style scoped>
/* .form-grid / .form-row-2 are global primitives (styles/main.css) — responsive there */
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
.select-with-add { display: flex; gap: 6px; align-items: flex-end; }
.flex-1 { flex: 1; }
</style>
