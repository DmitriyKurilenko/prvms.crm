<template>
  <FeatureGate feature="contracts">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Договоры и шаблоны</h1>
      </div>

      <div class="tabs-bar">
        <button :class="['tab-btn', { active: tab === 'contracts' }]" @click="tab = 'contracts'">Договоры</button>
        <button :class="['tab-btn', { active: tab === 'templates' }]" @click="tab = 'templates'">Шаблоны</button>
      </div>

      <!-- CONTRACTS TAB -->
      <div v-if="tab === 'contracts'" class="tab-content">
        <div class="toolbar">
          <PButton label="Сгенерировать договор" icon="pi pi-plus" size="small" @click="showGenerateForm = true" />
        </div>
        <PDataTable v-responsive-table :value="contracts" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="id" header="ID" />
          <PColumn field="template_name" header="Шаблон" />
          <PColumn field="status" header="Статус">
            <template #body="{ data }">
              <span :class="'status-badge status-' + data.status">{{ statusLabel(data.status) }}</span>
            </template>
          </PColumn>
          <PColumn field="created_at" header="Создан">
            <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <PButton icon="pi pi-eye" text size="small" @click="previewContract(data.id)" title="Просмотр" />
              <PButton icon="pi pi-download" text size="small" @click="downloadPdf(data.id)" title="Скачать PDF" />
              <PButton v-if="data.status === 'draft' || data.status === 'viewed'" icon="pi pi-send" text size="small" @click="openSendDialog(data)" title="Отправить на подпись" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- TEMPLATES TAB -->
      <div v-if="tab === 'templates'" class="tab-content">
        <div class="toolbar">
          <PButton label="Новый шаблон" icon="pi pi-plus" size="small" @click="openEditor(null)" />
        </div>
        <PDataTable v-responsive-table :value="templates" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="name" header="Название">
            <template #body="{ data }">
              {{ data.name }}
              <PTag v-if="data.is_system" value="Встроенный" severity="info" style="margin-left:6px;font-size:11px" />
            </template>
          </PColumn>
          <PColumn field="version" header="Версия" />
          <PColumn field="is_active" header="Активен">
            <template #body="{ data }">{{ data.is_active ? 'Да' : 'Нет' }}</template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <PButton icon="pi pi-pencil" text size="small" @click="openEditor(data)" title="Редактировать" />
              <PButton icon="pi pi-eye" text size="small" @click="previewTemplate(data.id)" title="Предпросмотр" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- TEMPLATE EDITOR DIALOG -->
      <PDialog v-model:visible="showEditor" :header="editorIsNew ? 'Новый шаблон' : 'Редактирование шаблона'" :style="{ width: '900px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div>
            <label class="field-label">Название *</label>
            <PInputText v-model="editorForm.name" class="w-full" />
          </div>
          <div>
            <label class="field-label">Содержимое шаблона</label>
            <div class="editor-toolbar">
              <PButton icon="pi pi-bold" text size="small" @click="editorCmd('bold')" title="Жирный" />
              <PButton icon="pi pi-italic" text size="small" @click="editorCmd('italic')" title="Курсив" />
              <PButton icon="pi pi-underline" text size="small" @click="editorCmd('underline')" title="Подчёркнутый" />
              <span class="toolbar-sep" />
              <PButton label="H1" text size="small" @click="editorCmd('formatBlock', 'h1')" />
              <PButton label="H2" text size="small" @click="editorCmd('formatBlock', 'h2')" />
              <PButton label="P" text size="small" @click="editorCmd('formatBlock', 'p')" />
              <span class="toolbar-sep" />
              <PButton icon="pi pi-list" text size="small" @click="editorCmd('insertUnorderedList')" title="Список" />
              <PButton icon="pi pi-table" text size="small" @click="insertTable" title="Таблица" />
              <span class="toolbar-sep" />
              <PSelect v-model="fieldToInsert" :options="dealFieldOptions" optionLabel="label" optionValue="value" placeholder="Вставить поле сделки" size="small" style="min-width:200px" @change="insertDealField" />
            </div>
            <div
              ref="editorRef"
              class="visual-editor"
              contenteditable="true"
              @input="onEditorInput"
              @paste="onEditorPaste"
              @blur="saveSelection"
              @keyup="saveSelection"
              @mouseup="saveSelection"
            />
          </div>
          <div style="display: flex; gap: 8px; justify-content: flex-end; align-items: center">
            <label style="font-size:13px"><input type="checkbox" v-model="editorForm.is_active" /> Активен</label>
            <PButton label="Сохранить" icon="pi pi-save" @click="saveTemplate" :disabled="!editorForm.name" />
          </div>
        </div>
      </PDialog>

      <!-- GENERATE CONTRACT DIALOG -->
      <PDialog v-model:visible="showGenerateForm" header="Генерация договора" :style="{ width: '450px' }" modal>
        <div class="form-grid">
          <div>
            <label class="field-label">Шаблон *</label>
            <PSelect v-model="genForm.template_id" :options="templateOptions" optionLabel="label" optionValue="value" placeholder="Выберите шаблон" class="w-full" />
          </div>
          <div>
            <label class="field-label">ID сделки</label>
            <PInputText v-model.number="genForm.deal_id" placeholder="Необязательно" type="number" class="w-full" />
          </div>
          <PButton label="Сгенерировать" @click="generateContract" :disabled="!genForm.template_id" />
        </div>
      </PDialog>

      <!-- SEND FOR SIGNING DIALOG -->
      <PDialog v-model:visible="showSendDialog" header="Отправить на подпись" :style="{ width: '500px' }" modal>
        <div class="form-grid">
          <p>Договор #{{ sendContract?.id }} — {{ statusLabel(sendContract?.status as string) }}</p>

          <template v-if="!signingUrl">
            <div>
              <label class="field-label">Телефон получателя</label>
              <PInputText v-model="sendRecipient" class="w-full" placeholder="+79001234567" />
            </div>
            <PButton label="Сформировать ссылку" icon="pi pi-link" @click="sendForSigning" :disabled="!sendRecipient" />
            <div v-if="signingError" class="send-result error">{{ signingError }}</div>
          </template>

          <template v-else>
            <div class="signing-link-box">
              <label class="field-label">Ссылка для подписания</label>
              <div style="display: flex; gap: 6px; align-items: center">
                <PInputText :modelValue="signingUrl" class="w-full" readonly />
                <PButton icon="pi pi-copy" text size="small" @click="copySigningLink" title="Скопировать ссылку" />
              </div>
              <p style="color: var(--text-muted); font-size: 12px; margin: 4px 0 0">Скопируйте ссылку и отправьте клиенту. Клиент откроет её, запросит код подтверждения и подпишет договор.</p>
            </div>
          </template>
        </div>
      </PDialog>

      <!-- PREVIEW DIALOG -->
      <PDialog v-model:visible="showPreview" header="Предпросмотр" :style="{ width: '700px' }" modal>
        <div v-html="previewHtml" class="contract-preview" />
      </PDialog>
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import FeatureGate from '@/components/FeatureGate.vue'
import { formatDate } from '@/utils/datetime'

const tab = ref('contracts')
const templates = ref<Array<Record<string, unknown>>>([])
const contracts = ref<Array<Record<string, unknown>>>([])

const templateOptions = computed(() =>
  templates.value.filter(t => t.is_active).map(t => ({ label: t.name as string, value: t.id as number }))
)
const signingMethodOptions = [
  { label: 'SMS OTP', value: 'sms_otp' },
]

/* --- Deal field options for the constructor --- */
const dealFieldOptions = [
  { label: '--- Сделка ---', value: '_h_deal', disabled: true },
  { label: 'ID сделки', value: 'deal_id' },
  { label: 'Название сделки', value: 'deal_name' },
  { label: 'Сумма', value: 'amount' },
  { label: 'Валюта', value: 'currency' },
  { label: 'Дата создания', value: 'created_at' },
  { label: '--- Контакт ---', value: '_h_contact', disabled: true },
  { label: 'Имя контакта', value: 'contact_name' },
  { label: 'Телефон контакта', value: 'contact.phone' },
  { label: 'Email контакта', value: 'contact.email' },
  { label: 'Должность', value: 'contact.position' },
  { label: '--- Компания ---', value: '_h_company', disabled: true },
  { label: 'Название компании', value: 'company_name' },
  { label: 'ИНН', value: 'company.inn' },
  { label: 'Телефон компании', value: 'company.phone' },
  { label: 'Email компании', value: 'company.email' },
  { label: 'Адрес', value: 'company.address' },
]

const load = async () => {
  templates.value = await api('/contracts/templates/')
  contracts.value = await api('/contracts/')
}

/* === Template Editor === */
const showEditor = ref(false)
const editorIsNew = ref(true)
const editorTemplateId = ref<number | null>(null)
const editorForm = reactive({ name: '', is_active: true })
const editorRef = ref<HTMLElement | null>(null)
const fieldToInsert = ref<string | null>(null)
let savedRange: Range | null = null

const saveSelection = () => {
  const sel = window.getSelection()
  if (sel && sel.rangeCount > 0 && editorRef.value?.contains(sel.anchorNode)) {
    savedRange = sel.getRangeAt(0).cloneRange()
  }
}

const restoreSelection = () => {
  if (savedRange) {
    const sel = window.getSelection()
    sel?.removeAllRanges()
    sel?.addRange(savedRange)
  }
}

const openEditor = async (tplData: Record<string, unknown> | null) => {
  if (tplData) {
    editorIsNew.value = false
    editorTemplateId.value = tplData.id as number
    editorForm.name = tplData.name as string
    editorForm.is_active = tplData.is_active as boolean
  } else {
    editorIsNew.value = true
    editorTemplateId.value = null
    editorForm.name = ''
    editorForm.is_active = true
  }
  showEditor.value = true
  await nextTick()
  if (editorRef.value) {
    editorRef.value.innerHTML = tplData
      ? (tplData.html_body as string) || ''
      : '<h1>Договор</h1><p>Текст договора...</p>'
  }
}

const editorCmd = (cmd: string, value?: string) => {
  document.execCommand(cmd, false, value)
  editorRef.value?.focus()
}

const insertTable = () => {
  const tableHtml = '<table style="width:100%;border-collapse:collapse">'
    + '<tr><td style="border:1px solid #ccc;padding:6px">Ячейка 1</td><td style="border:1px solid #ccc;padding:6px">Ячейка 2</td></tr>'
    + '<tr><td style="border:1px solid #ccc;padding:6px">Ячейка 3</td><td style="border:1px solid #ccc;padding:6px">Ячейка 4</td></tr>'
    + '</table><p></p>'
  document.execCommand('insertHTML', false, tableHtml)
  editorRef.value?.focus()
}

const insertDealField = () => {
  if (!fieldToInsert.value || fieldToInsert.value.startsWith('_h_')) return
  const tag = `{{ ${fieldToInsert.value} }}`
  restoreSelection()
  editorRef.value?.focus()
  document.execCommand(
    'insertHTML',
    false,
    `<span class="field-tag" contenteditable="false">${tag}</span>&nbsp;`,
  )
  fieldToInsert.value = null
  saveSelection()
}

const onEditorInput = () => { /* content tracked via editorRef */ }

const onEditorPaste = (e: ClipboardEvent) => {
  e.preventDefault()
  const text = e.clipboardData?.getData('text/html') || e.clipboardData?.getData('text/plain') || ''
  document.execCommand('insertHTML', false, text)
}

const getEditorHtml = (): string => editorRef.value?.innerHTML || ''

const extractVariables = (html: string): Array<{ key: string; sample: string }> => {
  const seen = new Set<string>()
  const result: Array<{ key: string; sample: string }> = []
  for (const m of html.matchAll(/\{\{\s*([\w.]+)\s*\}\}/g)) {
    const key = m[1]
    if (!seen.has(key)) {
      seen.add(key)
      const opt = dealFieldOptions.find(o => o.value === key)
      result.push({ key, sample: opt?.label || key })
    }
  }
  return result
}

const saveTemplate = async () => {
  const html = getEditorHtml()
  const variables = extractVariables(html)
  if (editorIsNew.value) {
    await api('/contracts/templates/', {
      method: 'POST',
      body: { name: editorForm.name, html_body: html, variable_schema: variables, is_active: editorForm.is_active },
    })
  } else {
    await api(`/contracts/templates/${editorTemplateId.value}/`, {
      method: 'PATCH',
      body: { name: editorForm.name, html_body: html, variable_schema: variables, is_active: editorForm.is_active },
    })
  }
  showEditor.value = false
  // Auto-save field mappings for variables (self-mapping by default)
  if (!editorIsNew.value && editorTemplateId.value) {
    const rows = variables.map(v => ({ variable_key: v.key, crm_field_path: v.key }))
    await api(`/contracts/templates/${editorTemplateId.value}/mappings/0/`, { method: 'PUT', body: rows })
  }
  await load()
}

/* === Generate === */
const showGenerateForm = ref(false)
const genForm = reactive({ template_id: null as number | null, deal_id: null as number | null, signing_method: 'sms_otp' })

const generateContract = async () => {
  if (!genForm.template_id) return
  const body: Record<string, unknown> = { template_id: genForm.template_id, signing_method: genForm.signing_method }
  if (genForm.deal_id) body.deal_id = genForm.deal_id
  await api('/contracts/generate', { method: 'POST', body })
  showGenerateForm.value = false
  genForm.template_id = null
  genForm.deal_id = null
  await load()
}

/* === Signing flow === */
const showSendDialog = ref(false)
const sendContract = ref<Record<string, unknown> | null>(null)
const sendRecipient = ref('')
const signingError = ref('')
const signingUrl = ref('')

const openSendDialog = (contract: Record<string, unknown>) => {
  sendContract.value = contract
  sendRecipient.value = (contract.contact_phone as string) || ''
  signingError.value = ''
  signingUrl.value = (contract.signing_url as string) || ''
  showSendDialog.value = true
}

const sendForSigning = async () => {
  if (!sendContract.value || !sendRecipient.value) return
  signingError.value = ''
  try {
    const result = await api<{ detail: string; token: string; signing_url: string }>(
      `/contracts/${sendContract.value.id}/send-for-signing/`,
      { method: 'POST', body: { recipient: sendRecipient.value } },
    )
    signingUrl.value = result.signing_url
    await load()
  } catch (e: unknown) {
    const err = e as { data?: { detail?: string } }
    signingError.value = err?.data?.detail || 'Ошибка отправки'
  }
}

const copySigningLink = () => {
  navigator.clipboard.writeText(signingUrl.value)
}

/* === Preview === */
const showPreview = ref(false)
const previewHtml = ref('')

const previewContract = async (id: number) => {
  const data = await api<{ html_snapshot: string }>(`/contracts/${id}/`)
  previewHtml.value = data.html_snapshot
  showPreview.value = true
}

const previewTemplate = async (templateId: number) => {
  const data = await api<{ html: string }>(`/contracts/templates/${templateId}/preview/`)
  previewHtml.value = data.html
  showPreview.value = true
}

const downloadPdf = (id: number) => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  const token = getAccessToken()
  const slug = getTenantSlug()
  window.open(`${apiUrl}/contracts/${id}/pdf/?token=${token}&tenant_slug=${slug}`, '_blank')
}

const statusLabel = (s: string) => {
  const map: Record<string, string> = { draft: 'Черновик', sent: 'Отправлен', viewed: 'Просмотрен', signed: 'Подписан', expired: 'Истёк' }
  return map[s] || s
}

onMounted(load)
</script>

<style scoped>
.tabs-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  flex-wrap: wrap;
  overflow-x: auto;
}

.tab-btn {
  padding: 8px 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-surface-0);
  color: var(--p-text-color);
  cursor: pointer;
  font-size: 14px;
}

.tab-btn.active {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  border-color: var(--p-primary-color);
}

.tab-content {
  min-height: 300px;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.form-grid {
  display: grid;
  gap: 10px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--p-text-color);
}

.w-full {
  width: 100%;
}

/* Visual editor */
.editor-toolbar {
  display: flex;
  gap: 2px;
  align-items: center;
  padding: 6px 8px;
  border: 1px solid var(--p-content-border-color);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--p-surface-50);
  flex-wrap: wrap;
}

.toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--p-content-border-color);
  margin: 0 4px;
}

.visual-editor {
  min-height: 300px;
  max-height: 500px;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0 0 8px 8px;
  background: var(--p-surface-0);
  font-size: 14px;
  line-height: 1.6;
  outline: none;
}

.visual-editor :deep(.field-tag) {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
  cursor: default;
}

/* Status badges */
.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status-draft { background: var(--p-surface-100); color: var(--p-text-color); }
.status-sent { background: #dbeafe; color: #1d4ed8; }
.status-viewed { background: #fef3c7; color: #92400e; }
.status-signed { background: #dcfce7; color: #16a34a; }
.status-expired { background: #fee2e2; color: #991b1b; }

.contract-preview {
  max-height: 500px;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
}

/* Signing flow */
.signing-link-box {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.test-otp-banner {
  background: #fef3c7;
  color: #92400e;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
}

.test-otp-banner code {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  margin-left: 4px;
}

.send-result.success {
  color: #16a34a;
  background: #dcfce7;
  padding: 8px;
  border-radius: 8px;
  text-align: center;
}

.send-result.error {
  color: #991b1b;
  background: #fee2e2;
  padding: 8px;
  border-radius: 8px;
  text-align: center;
}
</style>
