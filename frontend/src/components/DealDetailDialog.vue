<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    header="Сделка"
    :style="{ width: '640px', maxWidth: '95vw' }"
    modal
  >
    <div v-if="deal" class="form-grid">
      <div>
        <label class="field-label">Название *</label>
        <PInputText v-model="edit.name" class="w-full" :disabled="!canUpdate" />
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Сумма</label>
          <PInputText v-model.number="edit.amount" type="number" class="w-full" :disabled="!canUpdate" />
        </div>
        <div>
          <label class="field-label">Валюта</label>
          <PSelect v-model="edit.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" :disabled="!canUpdate" />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Контакт</label>
          <div class="select-with-add">
            <PSelect v-model="edit.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdate" />
            <PButton v-if="canCreateContact && canUpdate" icon="pi pi-plus" size="small" outlined @click="$emit('quickContact')" />
          </div>
        </div>
        <div>
          <label class="field-label">Компания</label>
          <div class="select-with-add">
            <PSelect v-model="edit.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdate" />
            <PButton v-if="canCreateCompany && canUpdate" icon="pi pi-plus" size="small" outlined @click="$emit('quickCompany')" />
          </div>
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Ответственный</label>
          <PSelect v-model="edit.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" :disabled="!canUpdate" />
        </div>
        <div>
          <label class="field-label">Дата закрытия</label>
          <PInputText v-model="edit.expected_close_date" type="date" class="w-full" :disabled="!canUpdate" />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Источник</label>
          <PSelect v-model="edit.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" :disabled="!canUpdate" />
        </div>
        <div>
          <label class="field-label">Причина проигрыша</label>
          <PInputText v-model="edit.loss_reason" class="w-full" :disabled="!canUpdate" />
        </div>
      </div>
      <div style="display: flex; gap: 8px; justify-content: flex-end">
        <PButton v-if="canUpdate" label="Сохранить" icon="pi pi-check" size="small" @click="$emit('save')" />
        <PButton v-if="canDelete" label="Удалить" icon="pi pi-trash" size="small" severity="danger" outlined @click="$emit('remove')" />
      </div>

      <!-- Contracts -->
      <div v-if="deal.contracts?.length" style="margin-top: 8px">
        <PDivider />
        <h4>Договоры</h4>
        <div v-for="c in deal.contracts" :key="c.id" class="contract-row">
          <span>📄 {{ c.template_name || 'Договор' }} #{{ c.id }}</span>
          <span :class="'status-badge status-' + c.status">{{ contractStatusLabel(c.status) }}</span>
          <span class="tl-date">{{ formatDate(c.created_at) }}</span>
          <PButton icon="pi pi-download" text size="small" @click="$emit('downloadPdf', c.id)" />
        </div>
      </div>

      <PDivider />
      <div class="activity-section">
        <h4>Лог активности</h4>
        <div class="activity-list">
          <div v-for="a in deal.activities" :key="a.id" class="timeline-item">
            <span class="tl-icon">{{ activityIcon(a.type) }}</span>
            <div class="tl-content">
              <strong>{{ a.title }}</strong>
              <div v-if="a.body" class="tl-body">{{ a.body }}</div>
              <div class="tl-meta">
                <span class="tl-date">{{ formatDateTime(a.created_at) }}</span>
                <PTag :value="activityTypeLabel(a.type)" size="small" />
              </div>
            </div>
          </div>
          <div v-if="!deal.activities?.length" class="empty-state">Нет активностей</div>
        </div>
        <div class="add-activity-row">
          <PSelect
            :modelValue="noteType"
            @update:modelValue="$emit('update:noteType', $event)"
            :options="activityTypeOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Тип"
            style="width: 150px"
            :disabled="!canUpdate"
          />
          <PInputText
            :modelValue="noteText"
            @update:modelValue="$emit('update:noteText', $event)"
            placeholder="Заметка..."
            style="flex: 1"
            :disabled="!canUpdate"
          />
          <PButton v-if="canUpdate" label="Добавить" size="small" @click="$emit('addNote')" />
        </div>
      </div>
    </div>
  </PDialog>
</template>

<script setup lang="ts">
import type { CrmActivity, CrmDeal } from '@/api/crm'
import { formatDate, formatDateTime } from '@/utils/datetime'

/**
 * Presentational shell for the deal-detail dialog. `edit` is the
 * parent's reactive object passed by reference — v-model mutates the
 * same proxy `saveDealEdit` reads. All actions bubble via emits;
 * `saveDealEdit`/`removeDeal`/`addNote`/`downloadPdf` stay in the parent.
 */
export interface DealEditModel {
  name: string
  amount: number | null
  currency: string
  contact_id: number | null
  company_id: number | null
  responsible_id: number | null
  expected_close_date: string
  source: string
  loss_reason: string
}
type NumOption = { label: string; value: number }
type StrOption = { label: string; value: string }

defineProps<{
  visible: boolean
  deal: (CrmDeal & { activities: CrmActivity[] }) | null
  edit: DealEditModel
  contactOptions: NumOption[]
  companyOptions: NumOption[]
  managerOptions: NumOption[]
  sourceOptions: StrOption[]
  currencies: StrOption[]
  activityTypeOptions: StrOption[]
  canUpdate: boolean
  canDelete: boolean
  canCreateContact: boolean
  canCreateCompany: boolean
  noteText: string
  noteType: string
}>()

defineEmits<{
  'update:visible': [boolean]
  'update:noteText': [string]
  'update:noteType': [string]
  save: []
  remove: []
  addNote: []
  quickContact: []
  quickCompany: []
  downloadPdf: [number]
}>()

const activityIcon = (type: string) => ({ call: '📞', message: '💬', task: '✅', note: '📝', email: '📧', contract: '📄', stage_change: '🔄', system: '⚙️' }[type] || '📌')
const activityTypeLabel = (type: string) => ({ call: 'Звонок', message: 'Сообщение', task: 'Задача', note: 'Заметка', email: 'Email', contract: 'Договор', stage_change: 'Смена стадии', system: 'Система' }[type] || type)
const contractStatusLabel = (s: string) => ({ draft: 'Черновик', sent: 'Отправлен', viewed: 'Просмотрен', signed: 'Подписан', expired: 'Истёк' }[s] || s)
</script>

<style scoped>
.form-grid { display: grid; gap: 12px; }
.form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
.select-with-add { display: flex; gap: 6px; align-items: flex-end; }
.flex-1 { flex: 1; }
.contract-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
.status-badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.status-draft { background: var(--surface-alt); }
.status-sent { background: #dbeafe; color: #1d4ed8; }
.status-viewed { background: #fef3c7; color: #92400e; }
.status-signed { background: #dcfce7; color: #16a34a; }
.status-expired { background: #fee2e2; color: #991b1b; }
.activity-section { display: flex; flex-direction: column; gap: 8px; }
.activity-section h4 { margin: 0; font-size: 14px; }
.activity-list { max-height: 200px; overflow-y: auto; }
.timeline-item { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.tl-icon { font-size: 16px; flex-shrink: 0; }
.tl-content { flex: 1; min-width: 0; }
.tl-body { font-size: 13px; color: var(--text-muted); margin-top: 2px; }
.tl-meta { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.tl-date { font-size: 12px; color: var(--text-muted); }
.add-activity-row { display: flex; gap: 6px; }
.empty-state { color: var(--text-muted); padding: 24px; text-align: center; }
</style>
