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
                <span v-if="(deal as any).contact_id" class="deal-contact">{{ contactLabel((deal as any).contact_id) }}</span>
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
        <PDataTable :value="flatDeals" size="small" stripedRows :paginator="flatDeals.length > 25" :rows="25">
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

    <!-- DEAL DETAIL DIALOG -->
    <PDialog v-model:visible="showDealDetail" header="Сделка" :style="{ width: '640px', maxWidth: '95vw' }" modal>
      <div v-if="dealDetail" class="form-grid">
        <div>
          <label class="field-label">Название *</label>
          <PInputText v-model="dealEdit.name" class="w-full" :disabled="!canUpdateDeal" />
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Сумма</label>
            <PInputText v-model.number="dealEdit.amount" type="number" class="w-full" :disabled="!canUpdateDeal" />
          </div>
          <div>
            <label class="field-label">Валюта</label>
            <PSelect v-model="dealEdit.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" :disabled="!canUpdateDeal" />
          </div>
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Контакт</label>
            <div class="select-with-add">
              <PSelect v-model="dealEdit.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdateDeal" />
              <PButton v-if="canCreateContact && canUpdateDeal" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'deal-contact'; showQuickContact = true" />
            </div>
          </div>
          <div>
            <label class="field-label">Компания</label>
            <div class="select-with-add">
              <PSelect v-model="dealEdit.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdateDeal" />
              <PButton v-if="canCreateCompany && canUpdateDeal" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'deal-company'; showQuickCompany = true" />
            </div>
          </div>
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Ответственный</label>
            <PSelect v-model="dealEdit.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" :disabled="!canUpdateDeal" />
          </div>
          <div>
            <label class="field-label">Дата закрытия</label>
            <PInputText v-model="dealEdit.expected_close_date" type="date" class="w-full" :disabled="!canUpdateDeal" />
          </div>
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Источник</label>
            <PSelect v-model="dealEdit.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" :disabled="!canUpdateDeal" />
          </div>
          <div>
            <label class="field-label">Причина проигрыша</label>
            <PInputText v-model="dealEdit.loss_reason" class="w-full" :disabled="!canUpdateDeal" />
          </div>
        </div>
        <div style="display: flex; gap: 8px; justify-content: flex-end">
          <PButton v-if="canUpdateDeal" label="Сохранить" icon="pi pi-check" size="small" @click="saveDealEdit" />
          <PButton v-if="canDeleteDeal" label="Удалить" icon="pi pi-trash" size="small" severity="danger" outlined @click="removeDeal" />
        </div>

        <!-- Contracts -->
        <div v-if="dealDetail.contracts?.length" style="margin-top: 8px">
          <PDivider />
          <h4>Договоры</h4>
          <div v-for="c in dealDetail.contracts" :key="c.id" class="contract-row">
            <span>📄 {{ c.template_name || 'Договор' }} #{{ c.id }}</span>
            <span :class="'status-badge status-' + c.status">{{ contractStatusLabel(c.status) }}</span>
            <span class="tl-date">{{ formatDate(c.created_at) }}</span>
            <PButton icon="pi pi-download" text size="small" @click="downloadPdf(c.id)" />
          </div>
        </div>

        <PDivider />
        <div class="activity-section">
          <h4>Лог активности</h4>
          <div class="activity-list">
            <div v-for="a in dealDetail.activities" :key="a.id" class="timeline-item">
              <span class="tl-icon">{{ activityIcon(a.type) }}</span>
              <div class="tl-content">
                <strong>{{ a.title }}</strong>
                <div v-if="(a as any).body" class="tl-body">{{ (a as any).body }}</div>
                <div class="tl-meta">
                  <span class="tl-date">{{ formatDateTime(a.created_at) }}</span>
                  <PTag :value="activityTypeLabel(a.type)" size="small" />
                </div>
              </div>
            </div>
            <div v-if="!dealDetail.activities?.length" class="empty-state">Нет активностей</div>
          </div>
          <div class="add-activity-row">
            <PSelect v-model="newActivityType" :options="activityTypeOptions" optionLabel="label" optionValue="value" placeholder="Тип" style="width: 150px" :disabled="!canUpdateDeal" />
            <PInputText v-model="newNote" placeholder="Заметка..." style="flex: 1" :disabled="!canUpdateDeal" />
            <PButton v-if="canUpdateDeal" label="Добавить" size="small" @click="addNote" />
          </div>
        </div>
      </div>
    </PDialog>

    <!-- NEW DEAL FORM -->
    <PDialog v-model:visible="showDealForm" header="Новая сделка" :style="{ width: '500px', maxWidth: '95vw' }" modal>
      <div class="form-grid">
        <div>
          <label class="field-label">Название *</label>
          <PInputText v-model="dealForm.name" placeholder="Название сделки" class="w-full" />
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Воронка *</label>
            <PSelect v-model="dealForm.pipeline_id" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Воронка" @change="onDealPipelineChange" class="w-full" />
          </div>
          <div>
            <label class="field-label">Стадия</label>
            <PSelect v-model="dealForm.stage_id" :options="dealFormStageOptions" optionLabel="label" optionValue="value" placeholder="Первая стадия" class="w-full" />
          </div>
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Сумма</label>
            <PInputText v-model.number="dealForm.amount" placeholder="0" type="number" class="w-full" />
          </div>
          <div>
            <label class="field-label">Валюта</label>
            <PSelect v-model="dealForm.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" />
          </div>
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Контакт</label>
            <div class="select-with-add">
              <PSelect v-model="dealForm.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
              <PButton v-if="canCreateContact" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'deal-contact'; showQuickContact = true" />
            </div>
          </div>
          <div>
            <label class="field-label">Компания</label>
            <div class="select-with-add">
              <PSelect v-model="dealForm.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
              <PButton v-if="canCreateCompany" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'deal-company'; showQuickCompany = true" />
            </div>
          </div>
        </div>
        <div class="form-row-2">
          <div>
            <label class="field-label">Ответственный</label>
            <PSelect v-model="dealForm.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" />
          </div>
          <div>
            <label class="field-label">Дата закрытия</label>
            <PInputText v-model="dealForm.expected_close_date" type="date" class="w-full" />
          </div>
        </div>
        <div>
          <label class="field-label">Источник</label>
          <PSelect v-model="dealForm.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" />
        </div>
        <PButton label="Создать" :disabled="!dealForm.name || !dealForm.pipeline_id" @click="submitDeal" />
      </div>
    </PDialog>

    <PDialog v-model:visible="showQuickContact" header="Быстрое создание контакта" :style="{ width: '400px', maxWidth: '95vw' }" modal>
      <div class="form-grid">
        <div class="form-row-2">
          <div><label class="field-label">Имя *</label><PInputText v-model="quickContact.first_name" placeholder="Имя" class="w-full" /></div>
          <div><label class="field-label">Фамилия</label><PInputText v-model="quickContact.last_name" placeholder="Фамилия" class="w-full" /></div>
        </div>
        <div class="form-row-2">
          <div><label class="field-label">Телефон</label><PInputText v-model="quickContact.phone" placeholder="+7..." class="w-full" /></div>
          <div><label class="field-label">Email</label><PInputText v-model="quickContact.email" placeholder="email@..." class="w-full" /></div>
        </div>
        <PButton label="Создать" @click="submitQuickContact" :disabled="!canCreateContact" />
      </div>
    </PDialog>

    <PDialog v-model:visible="showQuickCompany" header="Быстрое создание компании" :style="{ width: '400px', maxWidth: '95vw' }" modal>
      <div class="form-grid">
        <div><label class="field-label">Название *</label><PInputText v-model="quickCompany.name" placeholder="Название" class="w-full" /></div>
        <div class="form-row-2">
          <div><label class="field-label">ИНН</label><PInputText v-model="quickCompany.inn" placeholder="ИНН" maxlength="12" class="w-full" /></div>
          <div><label class="field-label">Телефон</label><PInputText v-model="quickCompany.phone" placeholder="+7..." class="w-full" /></div>
        </div>
        <PButton label="Создать" @click="submitQuickCompany" :disabled="!canCreateCompany" />
      </div>
    </PDialog>

    <template #locked>
      <div class="surface-card" style="padding: 16px">Раздел доступен в плане CRM.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmDeal, CrmActivity, KanbanColumn } from '@/api/crm'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'
import { formatDate, formatDateTime } from '@/utils/datetime'

const auth = useAuthStore()
const toast = useToast()
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
const contactLabel = (id: number) => contacts.value.find(c => c.id === id)?.first_name || ''

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
      if (filter.source && (d as any).source !== filter.source) return false
      if (filter.contact_id && (d as any).contact_id !== filter.contact_id) return false
      if (filter.company_id && (d as any).company_id !== filter.company_id) return false
      if (filter.date && (d as any).created_at) {
        const c = (d as any).created_at.slice(0, 10)
        if (filter.date === 'today' && c !== todayStr) return false
        if (filter.date === 'yesterday' && c !== yesterdayStr) return false
        if (filter.date === 'week' && new Date((d as any).created_at) < weekAgo) return false
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
  try {
    pipelines.value = await crmApi.listPipelines()
    if (pipelines.value.length && !selectedPipeline.value) {
      selectedPipeline.value = pipelines.value[0].id
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить воронки.', life: 5000 })
  }
}

const loadBoard = async () => {
  if (!selectedPipeline.value) return
  try {
    columns.value = await crmApi.kanbanDeals(selectedPipeline.value)
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить доску сделок.', life: 5000 })
  }
}

let dragDealId: number | null = null
const onDragStart = (e: DragEvent, id: number) => {
  dragDealId = id
  e.dataTransfer?.setData('text/plain', String(id))
}
const onDrop = async (_e: DragEvent, stageId: number) => {
  if (!canUpdateDeal.value || !dragDealId) return
  try {
    await crmApi.moveDeal(dragDealId, stageId)
    dragDealId = null
    await loadBoard()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось переместить сделку.', life: 5000 })
    dragDealId = null
  }
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

/* --- Deal detail --- */
const showDealDetail = ref(false)
const dealDetail = ref<(CrmDeal & { activities: CrmActivity[]; contracts?: any[] }) | null>(null)
const dealEdit = reactive({ name: '', amount: null as number | null, currency: 'RUB', contact_id: null as number | null, company_id: null as number | null, responsible_id: null as number | null, expected_close_date: '', source: '', loss_reason: '' })
const newNote = ref('')
const newActivityType = ref('note')

const openDeal = async (id: number) => {
  try {
    dealDetail.value = await crmApi.getDeal(id)
    const d = dealDetail.value
    Object.assign(dealEdit, { name: d.name, amount: d.amount, currency: d.currency, contact_id: d.contact_id, company_id: (d as any).company_id ?? null, responsible_id: d.responsible_id, expected_close_date: (d as any).expected_close_date || '', source: (d as any).source || '', loss_reason: (d as any).loss_reason || '' })
    showDealDetail.value = true
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось открыть сделку.', life: 5000 })
  }
}

const saveDealEdit = async () => {
  if (!canUpdateDeal.value || !dealDetail.value || !dealEdit.name) return
  try {
    await crmApi.patchDeal(dealDetail.value.id, { ...dealEdit, expected_close_date: dealEdit.expected_close_date || null })
    showDealDetail.value = false
    await loadBoard()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить сделку.', life: 5000 })
  }
}

const removeDeal = async () => {
  if (!canDeleteDeal.value || !dealDetail.value) return
  try {
    await crmApi.deleteDeal(dealDetail.value.id)
    showDealDetail.value = false
    await loadBoard()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить сделку.', life: 5000 })
  }
}

const addNote = async () => {
  if (!canUpdateDeal.value || !dealDetail.value || !newNote.value.trim()) return
  try {
    await crmApi.createActivity({ activity_type: newActivityType.value, deal_id: dealDetail.value.id, title: newNote.value })
    newNote.value = ''
    newActivityType.value = 'note'
    dealDetail.value = await crmApi.getDeal(dealDetail.value.id)
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось добавить заметку.', life: 5000 })
  }
}

const downloadPdf = (contractId: number) => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  window.open(`${apiUrl}/contracts/${contractId}/pdf/?token=${getAccessToken()}&tenant_slug=${getTenantSlug()}`, '_blank')
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
  try {
    await crmApi.createDeal({ name: dealForm.name, pipeline_id: dealForm.pipeline_id, stage_id: stageId, amount: dealForm.amount, currency: dealForm.currency, contact_id: dealForm.contact_id, company_id: dealForm.company_id, responsible_id: dealForm.responsible_id, expected_close_date: dealForm.expected_close_date || null, source: dealForm.source })
    showDealForm.value = false
    Object.assign(dealForm, { name: '', amount: null, currency: 'RUB', stage_id: null, contact_id: null, company_id: null, responsible_id: null, expected_close_date: '', source: '' })
    await loadBoard()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать сделку.', life: 5000 })
  }
}

/* --- Quick-create inline --- */
const quickCreateTarget = ref('')
const showQuickContact = ref(false)
const showQuickCompany = ref(false)
const quickContact = reactive({ first_name: '', last_name: '', phone: '', email: '' })
const quickCompany = reactive({ name: '', inn: '', phone: '' })

const submitQuickContact = async () => {
  if (!canCreateContact.value || !quickContact.first_name) return
  try {
    const res = await crmApi.createContact({ ...quickContact })
    await crmApi.listContacts().then(r => (contacts.value = r))
    if (quickCreateTarget.value === 'deal-contact') {
      if (showDealForm.value) dealForm.contact_id = res.id
      else dealEdit.contact_id = res.id
    }
    showQuickContact.value = false
    Object.assign(quickContact, { first_name: '', last_name: '', phone: '', email: '' })
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать контакт.', life: 5000 })
  }
}

const submitQuickCompany = async () => {
  if (!canCreateCompany.value || !quickCompany.name) return
  try {
    const res = await crmApi.createCompany({ ...quickCompany })
    await crmApi.listCompanies().then(r => (companies.value = r))
    if (quickCreateTarget.value === 'deal-company') {
      if (showDealForm.value) dealForm.company_id = res.id
      else dealEdit.company_id = res.id
    }
    showQuickCompany.value = false
    Object.assign(quickCompany, { name: '', inn: '', phone: '' })
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать компанию.', life: 5000 })
  }
}

/* --- Helpers --- */
const activityIcon = (type: string) => ({ call: '📞', message: '💬', task: '✅', note: '📝', email: '📧', contract: '📄', stage_change: '🔄', system: '⚙️' }[type] || '📌')
const activityTypeLabel = (type: string) => ({ call: 'Звонок', message: 'Сообщение', task: 'Задача', note: 'Заметка', email: 'Email', contract: 'Договор', stage_change: 'Смена стадии', system: 'Система' }[type] || type)
const contractStatusLabel = (s: string) => ({ draft: 'Черновик', sent: 'Отправлен', viewed: 'Просмотрен', signed: 'Подписан', expired: 'Истёк' }[s] || s)
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

/* Form */
.form-grid { display: grid; gap: 12px; }
.form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
.select-with-add { display: flex; gap: 6px; align-items: flex-end; }
.flex-1 { flex: 1; }
.empty-state { color: var(--text-muted); padding: 24px; text-align: center; }
</style>
