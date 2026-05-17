<template>
  <FeatureGate feature="crm_builtin" class="view-gate">
    <section class="deals-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Сделки</h1>
        <div style="display: flex; gap: 8px; align-items: center">
          <PSelect
            v-model="selectedPipeline"
            :options="pipelines"
            optionLabel="name"
            optionValue="id"
            placeholder="Воронка"
            style="min-width: 180px"
            @change="loadBoard"
          />
          <PButton
            :icon="viewMode === 'board' ? 'pi pi-list' : 'pi pi-th-large'"
            size="small"
            outlined
            @click="viewMode = viewMode === 'board' ? 'list' : 'board'"
          />
          <PButton
            icon="pi pi-filter"
            size="small"
            :outlined="!showFilters"
            @click="showFilters = !showFilters"
          />
          <PButton
            v-if="canCreateDeal"
            label="Новая сделка"
            icon="pi pi-plus"
            size="small"
            @click="openDealForm"
          />
        </div>
      </div>

      <!-- Kanban Filters -->
      <div v-if="showFilters" class="kanban-filters animate-fade">
        <PSelect v-model="filter.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="Источник" showClear class="filter-field" />
        <PSelect v-model="filter.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="Контакт" showClear filter filterPlaceholder="Поиск…" class="filter-field" />
        <PSelect v-model="filter.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="Компания" showClear filter filterPlaceholder="Поиск…" class="filter-field" />
        <PSelect v-model="filter.date" :options="dateFilterOptions" optionLabel="label" optionValue="value" placeholder="Дата" showClear class="filter-field" />
      </div>

      <!-- Board view -->
      <div v-if="viewMode === 'board'" class="kanban-board">
        <div
          v-for="col in filteredColumns"
          :key="col.stage.id"
          class="kanban-col surface-card"
          @dragover.prevent
          @drop="onDrop($event, col.stage.id)"
        >
          <div class="col-header">
            <span class="stage-dot" :style="{ background: col.stage.color }" />
            <span class="col-name">{{ col.stage.name }}</span>
            <span class="col-count">{{ col.deals.length }}</span>
          </div>
          <div class="col-amount">{{ colTotal(col) }}</div>
          <div class="col-body">
            <div
              v-for="deal in col.deals"
              :key="deal.id"
              class="deal-card surface-card"
              :draggable="canUpdateDeal"
              @dragstart="canUpdateDeal && onDragStart($event, deal.id)"
              @click="openDeal(deal.id)"
            >
              <div class="deal-name">{{ deal.name }}</div>
              <div v-if="deal.amount" class="deal-amount">{{ deal.amount.toLocaleString('ru') }} {{ deal.currency }}</div>
              <div class="deal-meta">
                <span v-if="deal.contact_id" class="deal-contact">{{ contactLabel(deal.contact_id) }}</span>
              </div>
            </div>
          </div>
          <button v-if="canCreateDeal" class="add-deal-btn" @click="openDealFormForStage(col.stage.id)">
            <i class="pi pi-plus" /> Добавить
          </button>
        </div>
        <div v-if="!columns.length" class="empty-state">Выберите воронку</div>
      </div>

      <!-- List view -->
      <div v-else class="surface-card" style="overflow: auto">
        <PDataTable v-responsive-table :value="flatDeals" size="small" stripedRows :paginator="flatDeals.length > 25" :rows="25">
          <PColumn field="name" header="Сделка" sortable>
            <template #body="{ data }">
              <a class="deal-link" @click.prevent="openDeal(data.id)">{{ data.name }}</a>
            </template>
          </PColumn>
          <PColumn field="stage_name" header="Этап" sortable>
            <template #body="{ data }">
              <span class="stage-dot" :style="{ background: data._stage_color }" />
              {{ data.stage_name }}
            </template>
          </PColumn>
          <PColumn field="amount" header="Сумма" sortable>
            <template #body="{ data }">
              {{ data.amount ? data.amount.toLocaleString('ru') + ' ' + data.currency : '—' }}
            </template>
          </PColumn>
          <PColumn field="source" header="Источник" sortable />
          <PColumn field="created_at" header="Дата" sortable>
            <template #body="{ data }">{{ data.created_at ? formatDate(data.created_at) : '' }}</template>
          </PColumn>
        </PDataTable>
      </div>
    </section>

    <DealFormDialog
      :visible="showDealForm"
      :form="dealForm"
      :pipelines="pipelines"
      :stage-options="dealFormStageOptions"
      :contact-options="contactOptions"
      :company-options="companyOptions"
      :manager-options="managerOptions"
      :source-options="sourceOptions"
      :currencies="currencies"
      :can-create-contact="canCreateContact"
      :can-create-company="canCreateCompany"
      @update:visible="showDealForm = $event"
      @submit="submitDeal"
      @pipeline-change="onDealPipelineChange"
      @quick-contact="quickCreateTarget = 'deal-contact'; showQuickContact = true"
      @quick-company="quickCreateTarget = 'deal-company'; showQuickCompany = true"
    />

    <QuickContactDialog
      :visible="showQuickContact"
      :can-create="canCreateContact"
      @update:visible="showQuickContact = $event"
      @created="onQuickContactCreated"
    />

    <QuickCompanyDialog
      :visible="showQuickCompany"
      :can-create="canCreateCompany"
      @update:visible="showQuickCompany = $event"
      @created="onQuickCompanyCreated"
    />

    <template #locked>
      <div class="surface-card" style="padding: 16px">Раздел доступен в плане CRM.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useApiCall } from '@/composables/useApiCall'
import FeatureGate from '@/components/FeatureGate.vue'
import QuickContactDialog from '@/components/QuickContactDialog.vue'
import QuickCompanyDialog from '@/components/QuickCompanyDialog.vue'
import DealFormDialog from '@/components/DealFormDialog.vue'
import * as crmApi from '@/api/crm'
import type { CrmDeal, KanbanColumn } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'
import { formatDate } from '@/utils/datetime'

const auth = useAuthStore()
const router = useRouter()
const { call } = useApiCall()
const perms = computed(() => normalizeCrmPermissions(auth.user?.crm_permissions))
const canCreateDeal = computed(() => perms.value.deals.can_create)
const canUpdateDeal = computed(() => perms.value.deals.can_update)
const canDeleteDeal = computed(() => perms.value.deals.can_delete)
const canCreateContact = computed(() => perms.value.contacts.can_create)
const canCreateCompany = computed(() => perms.value.companies.can_create)

const sourceOptions = [
  { label: 'Сайт', value: 'website' }, { label: 'Телефон', value: 'phone' },
  { label: 'Email', value: 'email' }, { label: 'Соцсети', value: 'social' },
  { label: 'Рекомендация', value: 'referral' }, { label: 'Реклама', value: 'ad' },
  { label: 'Другое', value: 'other' },
]
const currencies = [{ label: 'RUB', value: 'RUB' }, { label: 'USD', value: 'USD' }, { label: 'EUR', value: 'EUR' }]
const dateFilterOptions = [{ label: 'Сегодня', value: 'today' }, { label: 'Вчера', value: 'yesterday' }, { label: 'Неделя', value: 'week' }]
const activityTypeOptions = [
  { label: '📝 Заметка', value: 'note' }, { label: '📞 Звонок', value: 'call' },
  { label: '💬 Сообщение', value: 'message' }, { label: '📧 Email', value: 'email' },
]

/* --- Data --- */
const pipelines = ref<crmApi.CrmPipeline[]>([])
const selectedPipeline = ref<number | null>(null)
const columns = ref<KanbanColumn[]>([])
const contacts = ref<crmApi.CrmContact[]>([])
const companies = ref<crmApi.CrmCompany[]>([])
const managers = ref<{ id: number; name: string }[]>([])
const viewMode = ref<'board' | 'list'>('board')
const showFilters = ref(false)
const filter = reactive({ source: null as string | null, contact_id: null as number | null, company_id: null as number | null, date: null as string | null })

const contactOptions = computed(() => contacts.value.map(c => ({ label: `${c.first_name} ${c.last_name}`.trim(), value: c.id })))
const companyOptions = computed(() => companies.value.map(c => ({ label: c.name, value: c.id })))
const managerOptions = computed(() => managers.value.map(m => ({ label: m.name, value: m.id })))
const contactLabel = (id: number | null | undefined) => contacts.value.find(c => c.id === id)?.first_name || ''

const filteredColumns = computed(() => {
  const hasF = filter.source || filter.contact_id || filter.company_id || filter.date
  if (!hasF) return columns.value
  const now = new Date()
  const todayStr = now.toISOString().slice(0, 10)
  const yesterdayStr = new Date(now.getTime() - 86400000).toISOString().slice(0, 10)
  const weekAgo = new Date(now.getTime() - 7 * 86400000)
  return columns.value.map(col => ({
    ...col,
    deals: col.deals.filter(d => {
      if (filter.source && d.source !== filter.source) return false
      if (filter.contact_id && d.contact_id !== filter.contact_id) return false
      if (filter.company_id && d.company_id !== filter.company_id) return false
      if (filter.date && d.created_at) {
        const c = d.created_at.slice(0, 10)
        if (filter.date === 'today' && c !== todayStr) return false
        if (filter.date === 'yesterday' && c !== yesterdayStr) return false
        if (filter.date === 'week' && new Date(d.created_at) < weekAgo) return false
      }
      return true
    })
  }))
})

const flatDeals = computed(() => {
  const result: Record<string, unknown>[] = []
  for (const col of filteredColumns.value) {
    for (const d of col.deals) {
      result.push({ ...d, stage_name: col.stage.name, _stage_color: col.stage.color })
    }
  }
  return result
})

const colTotal = (col: KanbanColumn) => {
  const sum = col.deals.reduce((s, d) => s + (d.amount || 0), 0)
  return sum ? sum.toLocaleString('ru') + ' ₽' : ''
}

const loadPipelines = async () => {
  const res = await call(() => crmApi.listPipelines(), 'Не удалось загрузить воронки.')
  if (res === undefined) return
  pipelines.value = res
  if (pipelines.value.length && !selectedPipeline.value) {
    selectedPipeline.value = pipelines.value[0].id
  }
}

const loadBoard = async () => {
  if (!selectedPipeline.value) return
  const pid = selectedPipeline.value
  const res = await call(() => crmApi.kanbanDeals(pid), 'Не удалось загрузить доску сделок.')
  if (res !== undefined) columns.value = res
}

let dragDealId: number | null = null
const onDragStart = (e: DragEvent, id: number) => {
  dragDealId = id
  e.dataTransfer?.setData('text/plain', String(id))
}
const onDrop = async (_e: DragEvent, stageId: number) => {
  if (!canUpdateDeal.value || !dragDealId) return
  const id = dragDealId
  const res = await call(() => crmApi.moveDeal(id, stageId), 'Не удалось переместить сделку.')
  dragDealId = null
  if (res !== undefined) await loadBoard()
}

onMounted(async () => {
  await loadPipelines()
  await Promise.all([
    loadBoard(),
    crmApi.listContacts().then(r => (contacts.value = r)),
    crmApi.listCompanies().then(r => (companies.value = r)),
    crmApi.listManagers().then(r => (managers.value = r)),
  ])
})

const openDeal = (id: number) => {
  router.push(`/app/deals/${id}`)
}

/* --- New deal form --- */
const showDealForm = ref(false)
const dealForm = reactive({ name: '', pipeline_id: null as number | null, stage_id: null as number | null, amount: null as number | null, currency: 'RUB', contact_id: null as number | null, company_id: null as number | null, responsible_id: null as number | null, expected_close_date: '', source: '' })
const dealFormStages = ref<crmApi.CrmStage[]>([])
const dealFormStageOptions = computed(() => dealFormStages.value.map(s => ({ label: s.name, value: s.id })))

const openDealForm = async () => {
  if (!dealForm.pipeline_id && selectedPipeline.value) dealForm.pipeline_id = selectedPipeline.value
  if (dealForm.pipeline_id) dealFormStages.value = await crmApi.listStages(dealForm.pipeline_id)
  showDealForm.value = true
}

const openDealFormForStage = async (stageId: number) => {
  if (!canCreateDeal.value) return
  dealForm.stage_id = stageId
  await openDealForm()
}

const onDealPipelineChange = async () => {
  dealForm.stage_id = null
  if (dealForm.pipeline_id) dealFormStages.value = await crmApi.listStages(dealForm.pipeline_id)
  else dealFormStages.value = []
}

const submitDeal = async () => {
  if (!canCreateDeal.value || !dealForm.name || !dealForm.pipeline_id) return
  let stageId = dealForm.stage_id
  if (!stageId) {
    const stages = dealFormStages.value.length ? dealFormStages.value : await crmApi.listStages(dealForm.pipeline_id)
    stageId = stages[0]?.id || null
  }
  if (!stageId) return
  const res = await call(
    () => crmApi.createDeal({ name: dealForm.name, pipeline_id: dealForm.pipeline_id, stage_id: stageId, amount: dealForm.amount, currency: dealForm.currency, contact_id: dealForm.contact_id, company_id: dealForm.company_id, responsible_id: dealForm.responsible_id, expected_close_date: dealForm.expected_close_date || null, source: dealForm.source }),
    'Не удалось создать сделку.',
  )
  if (res === undefined) return
  showDealForm.value = false
  Object.assign(dealForm, { name: '', amount: null, currency: 'RUB', stage_id: null, contact_id: null, company_id: null, responsible_id: null, expected_close_date: '', source: '' })
  await loadBoard()
}

/* --- Quick-create (dialogs extracted to child components) --- */
const quickCreateTarget = ref('')
const showQuickContact = ref(false)
const showQuickCompany = ref(false)

const onQuickContactCreated = async (res: { id: number }) => {
  const list = await call(() => crmApi.listContacts(), 'Не удалось создать контакт.')
  if (list !== undefined) contacts.value = list
  if (quickCreateTarget.value === 'deal-contact') {
    dealForm.contact_id = res.id
  }
}

const onQuickCompanyCreated = async (res: { id: number }) => {
  const list = await call(() => crmApi.listCompanies(), 'Не удалось создать компанию.')
  if (list !== undefined) companies.value = list
  if (quickCreateTarget.value === 'deal-company') {
    dealForm.company_id = res.id
  }
}

</script>

<style scoped>
.view-gate,
:deep(.view-gate > div) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.deals-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.kanban-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-field {
  min-width: 160px;
}

/* Kanban board */
.kanban-board {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  flex: 1;
  min-height: 0;
}

.kanban-col {
  min-width: 260px;
  max-width: 300px;
  flex: 0 0 auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.col-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.stage-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.col-name {
  font-weight: 700;
  font-size: 13px;
  flex: 1;
}

.col-count {
  background: var(--surface-alt);
  border-radius: 99px;
  padding: 1px 8px;
  font-size: 12px;
  font-weight: 600;
}

.col-amount {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
  min-height: 16px;
}

.col-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.deal-card {
  padding: 12px;
  cursor: grab;
  border: 1px solid var(--line);
  transition: box-shadow 0.15s, transform 0.1s;
}

.deal-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
  border-color: var(--brand);
}

.deal-name {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 4px;
}

.deal-amount {
  font-size: 13px;
  color: var(--brand);
  font-weight: 700;
}

.deal-meta {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
}

.deal-contact { }

.add-deal-btn {
  width: 100%;
  padding: 8px;
  border: 1.5px dashed var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  font-family: 'Nunito Sans', sans-serif;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.15s;
  flex-shrink: 0;
}

.add-deal-btn:hover {
  background: var(--surface-alt);
  border-color: var(--brand);
  color: var(--brand);
}

/* Deal link */
.deal-link {
  color: var(--brand);
  cursor: pointer;
  font-weight: 600;
}

.deal-link:hover { text-decoration: underline; }

/* Contracts */
.contract-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}

/* Status badges */
.status-badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.status-draft { background: var(--surface-alt); }
.status-sent { background: #dbeafe; color: #1d4ed8; }
.status-viewed { background: #fef3c7; color: #92400e; }
.status-signed { background: #dcfce7; color: #16a34a; }
.status-expired { background: #fee2e2; color: #991b1b; }

/* Activity */
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

/* Form — .form-grid / .form-row-2 are global primitives (styles/main.css), responsive there */
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
.select-with-add { display: flex; gap: 6px; align-items: flex-end; }
.flex-1 { flex: 1; }
.empty-state { color: var(--text-muted); padding: 24px; text-align: center; }
</style>
