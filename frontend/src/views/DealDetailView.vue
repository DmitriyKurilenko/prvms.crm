<template>
  <FeatureGate feature="crm_builtin" class="view-gate">
    <section v-if="deal" class="deal-detail-page animate-fade">
      <div class="section-header">
        <div class="deal-header-left">
          <PButton icon="pi pi-arrow-left" text size="small" @click="goBack" />
          <h1 class="page-title">{{ deal.name }}</h1>
          <PTag :value="stageLabel" severity="info" />
        </div>
        <div style="display: flex; gap: 8px; align-items: center">
          <PButton v-if="canCall && dealContactPhone" label="Позвонить" icon="pi pi-phone" size="small" severity="success" outlined @click="callContact" />
          <PButton v-if="canUpdateDeal" label="Сохранить" icon="pi pi-check" size="small" @click="saveDealEdit" />
          <PButton v-if="canDeleteDeal" label="Удалить" icon="pi pi-trash" size="small" severity="danger" outlined @click="removeDeal" />
        </div>
      </div>

      <div class="deal-layout">
        <!-- Left column -->
        <div class="deal-main surface-card">
          <div class="deal-tabs">
            <button v-for="t in tabs" :key="t.id" class="deal-tab" :class="{ active: activeTab === t.id }" @click="activeTab = t.id">
              {{ t.label }}
            </button>
          </div>

          <!-- Info tab -->
          <div v-if="activeTab === 'info'" class="tab-pane animate-fade">
            <div class="form-grid">
              <div>
                <label class="field-label">Название *</label>
                <PInputText v-model="edit.name" class="w-full" :disabled="!canUpdateDeal" />
              </div>
              <div class="form-row-2">
                <div>
                  <label class="field-label">Сумма</label>
                  <PInputText v-model.number="edit.amount" type="number" class="w-full" :disabled="!canUpdateDeal || dealItems.has_items" />
                  <small v-if="dealItems.has_items" class="amount-hint">Сумма рассчитана по позициям</small>
                </div>
                <div>
                  <label class="field-label">Валюта</label>
                  <PSelect v-model="edit.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" :disabled="!canUpdateDeal" />
                </div>
              </div>
              <div class="form-row-2">
                <div>
                  <label class="field-label">Контакт</label>
                  <div class="select-with-add">
                    <PSelect v-model="edit.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdateDeal" />
                    <PButton v-if="canCreateContact && canUpdateDeal" icon="pi pi-plus" size="small" outlined @click="openQuickContact" />
                  </div>
                </div>
                <div>
                  <label class="field-label">Компания</label>
                  <div class="select-with-add">
                    <PSelect v-model="edit.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdateDeal" />
                    <PButton v-if="canCreateCompany && canUpdateDeal" icon="pi pi-plus" size="small" outlined @click="openQuickCompany" />
                  </div>
                </div>
              </div>
              <div class="form-row-2">
                <div>
                  <label class="field-label">Ответственный</label>
                  <PSelect v-model="edit.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" :disabled="!canUpdateDeal" />
                </div>
                <div>
                  <label class="field-label">Дата закрытия</label>
                  <PInputText v-model="edit.expected_close_date" type="date" class="w-full" :disabled="!canUpdateDeal" />
                </div>
              </div>
              <div class="form-row-2">
                <div>
                  <label class="field-label">Источник</label>
                  <PSelect v-model="edit.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" :disabled="!canUpdateDeal" />
                </div>
                <div>
                  <label class="field-label">Причина проигрыша</label>
                  <PInputText v-model="edit.loss_reason" class="w-full" :disabled="!canUpdateDeal" />
                </div>
              </div>

              <!-- Tags -->
              <div class="deal-tags-block">
                <label class="field-label">Теги</label>
                <div class="tag-chips">
                  <span v-for="t in deal.tags || []" :key="t.id" class="tag-chip" :style="{ background: t.color }">{{ t.name }}</span>
                  <span v-if="!(deal.tags || []).length" class="tags-empty">—</span>
                </div>
                <PMultiSelect
                  v-if="canUpdateDeal"
                  v-model="dealTagIds"
                  :options="allTags"
                  optionLabel="name"
                  optionValue="id"
                  placeholder="Назначить теги"
                  filter
                  class="w-full"
                  @change="saveDealTags"
                />
              </div>

              <!-- Documents -->
              <div v-if="deal.documents?.length" style="margin-top: 8px">
                <PDivider />
                <h4>Документы</h4>
                <div v-for="c in deal.documents" :key="c.id" class="document-row">
                  <span>📄 {{ c.template_name || 'Документ' }} #{{ c.id }}</span>
                  <span :class="'status-badge status-' + c.status">{{ documentStatusLabel(c.status) }}</span>
                  <span class="tl-date">{{ formatDate(c.created_at) }}</span>
                  <PButton icon="pi pi-download" text size="small" @click="downloadPdf(c.id)" />
                </div>
              </div>
            </div>
          </div>

          <!-- Activity tab -->
          <div v-if="activeTab === 'activity'" class="tab-pane animate-fade">
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
                <PSelect v-model="newActivityType" :options="activityTypeOptions" optionLabel="label" optionValue="value" placeholder="Тип" style="width: 150px" :disabled="!canUpdateDeal" />
                <PInputText v-model="newNote" placeholder="Заметка..." style="flex: 1" :disabled="!canUpdateDeal" />
                <PButton v-if="canUpdateDeal" label="Добавить" size="small" @click="addNote" />
              </div>
            </div>
          </div>

          <!-- Items tab -->
          <div v-if="activeTab === 'items'" class="tab-pane animate-fade">
            <div class="items-section">
              <div v-if="canUpdateDeal" class="add-item-row">
                <PSelect
                  v-model="newItem.product_id"
                  :options="productOptions"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Выберите товар"
                  filter
                  filterPlaceholder="Поиск…"
                  class="flex-1"
                />
                <PInputNumber v-model="newItem.quantity" :min="0" :minFractionDigits="0" :maxFractionDigits="3" placeholder="Кол-во" style="width: 120px" />
                <PButton label="Добавить" icon="pi pi-plus" size="small" :disabled="!newItem.product_id" @click="addItem" />
              </div>

              <PDataTable v-responsive-table :value="dealItems.items" size="small" stripedRows class="items-table">
                <PColumn field="name" header="Наименование" />
                <PColumn header="Кол-во">
                  <template #body="{ data }">{{ data.quantity }}</template>
                </PColumn>
                <PColumn header="Цена">
                  <template #body="{ data }">{{ formatMoney(data.price) }}</template>
                </PColumn>
                <PColumn header="НДС">
                  <template #body="{ data }">{{ data.vat_rate }}%</template>
                </PColumn>
                <PColumn header="Сумма">
                  <template #body="{ data }">{{ formatMoney(data.line_total) }}</template>
                </PColumn>
                <PColumn header="" style="width: 60px">
                  <template #body="{ data }">
                    <PButton v-if="canUpdateDeal" icon="pi pi-trash" text size="small" severity="danger" @click="removeItem(data.id)" />
                  </template>
                </PColumn>
                <template #empty>
                  <div class="empty-state">Нет позиций</div>
                </template>
              </PDataTable>

              <div v-if="dealItems.has_items" class="items-totals">
                <div><span>Без НДС:</span> <strong>{{ formatMoney(dealItems.subtotal) }} {{ deal.currency }}</strong></div>
                <div><span>НДС:</span> <strong>{{ formatMoney(dealItems.vat) }} {{ deal.currency }}</strong></div>
                <div class="grand"><span>Итого:</span> <strong>{{ formatMoney(dealItems.total) }} {{ deal.currency }}</strong></div>
              </div>
            </div>
          </div>

          <!-- Chat tab -->
          <div v-if="activeTab === 'chat'" class="tab-pane animate-fade">
            <DealChatTab
              ref="chatTabRef"
              :sessions="chatSessions"
              :session-options="chatSessionOptions"
              :selected-session-id="selectedChatSessionId"
              :messages="chatMessages"
              :message-text="chatMessageText"
              :can-send="canUpdateDeal"
              @update:selected-session-id="selectedChatSessionId = $event"
              @update:message-text="chatMessageText = $event"
              @send-message="sendChatMessage"
            />
          </div>
        </div>
      </div>
    </section>

    <QuickContactDialog :visible="showQuickContact" :can-create="canCreateContact" @update:visible="showQuickContact = $event" @created="onQuickContactCreated" />
    <QuickCompanyDialog :visible="showQuickCompany" :can-create="canCreateCompany" @update:visible="showQuickCompany = $event" @created="onQuickCompanyCreated" />

    <template #locked>
      <div class="surface-card" style="padding: 16px">Раздел доступен в плане CRM.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiCall } from '@/composables/useApiCall'
import FeatureGate from '@/components/FeatureGate.vue'
import DealChatTab from '@/components/DealChatTab.vue'
import QuickContactDialog from '@/components/QuickContactDialog.vue'
import QuickCompanyDialog from '@/components/QuickCompanyDialog.vue'
import * as crmApi from '@/api/crm'
import type { CrmActivity, CrmDeal, CrmTag } from '@/api/crm'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import { refresh as refreshToken } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { usePhoneStore } from '@/stores/phone'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'
import { formatDate, formatDateTime } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const tenantStore = useTenantStore()
const phone = usePhoneStore()
const { call } = useApiCall()
const canCall = computed(() => tenantStore.hasFeature('telephony'))

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
const activityTypeOptions = [
  { label: '📝 Заметка', value: 'note' }, { label: '📞 Звонок', value: 'call' },
  { label: '💬 Сообщение', value: 'message' }, { label: '📧 Email', value: 'email' },
]

/* --- Data --- */
const deal = ref<(CrmDeal & { activities: CrmActivity[] }) | null>(null)
const edit = reactive({ name: '', amount: null as number | null, currency: 'RUB', contact_id: null as number | null, company_id: null as number | null, responsible_id: null as number | null, expected_close_date: '', source: '', loss_reason: '' })
const newNote = ref('')
const newActivityType = ref('note')

const allTags = ref<CrmTag[]>([])
const dealTagIds = ref<number[]>([])

const contacts = ref<crmApi.CrmContact[]>([])
const companies = ref<crmApi.CrmCompany[]>([])
const managers = ref<{ id: number; name: string }[]>([])

/* --- Deal items (catalog) --- */
const products = ref<crmApi.CrmProduct[]>([])
const dealItems = reactive<crmApi.CrmDealItems>({ items: [], subtotal: 0, vat: 0, total: 0, has_items: false })
const newItem = reactive({ product_id: null as number | null, quantity: 1 })
const productOptions = computed(() =>
  products.value.filter(p => p.is_active).map(p => ({ label: `${p.name} — ${p.price} ${p.currency}`, value: p.id })),
)
const formatMoney = (v: number) => Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const dealContactPhone = computed(() => contacts.value.find(c => c.id === deal.value?.contact_id)?.phone || '')
const callContact = () => {
  if (dealContactPhone.value) phone.call(dealContactPhone.value, { dealId: deal.value?.id, contactId: deal.value?.contact_id ?? undefined })
}
const contactOptions = computed(() => contacts.value.map(c => ({ label: `${c.first_name} ${c.last_name}`.trim(), value: c.id })))
const companyOptions = computed(() => companies.value.map(c => ({ label: c.name, value: c.id })))
const managerOptions = computed(() => managers.value.map(m => ({ label: m.name, value: m.id })))

const stageLabel = computed(() => {
  if (!deal.value?.stage_name) return ''
  return deal.value.stage_name
})

const tabs = [
  { id: 'info', label: 'Инфо' },
  { id: 'items', label: 'Позиции' },
  { id: 'activity', label: 'Активность' },
  { id: 'chat', label: 'Чат' },
]
const activeTab = ref('info')

const dealId = computed(() => Number(route.params.id))

const loadDeal = async () => {
  const id = dealId.value
  if (!id) return
  const d = await call(() => crmApi.getDeal(id), 'Не удалось загрузить сделку.')
  if (d === undefined) return
  deal.value = d
  Object.assign(edit, {
    name: d.name,
    amount: d.amount,
    currency: d.currency,
    contact_id: d.contact_id,
    company_id: d.company_id ?? null,
    responsible_id: d.responsible_id,
    expected_close_date: d.expected_close_date || '',
    source: d.source || '',
    loss_reason: d.loss_reason || '',
  })
  dealTagIds.value = (d.tags || []).map(t => t.id)
  // auto-select first chat session when opening chat tab
  if (d.chat_sessions?.length && !selectedChatSessionId.value) {
    selectedChatSessionId.value = d.chat_sessions[0].id
  }
}

const loadItems = async () => {
  const id = dealId.value
  if (!id) return
  const res = await call(() => crmApi.listDealItems(id), 'Не удалось загрузить позиции.')
  if (res === undefined) return
  Object.assign(dealItems, res)
}

const addItem = async () => {
  if (!canUpdateDeal.value || !deal.value || !newItem.product_id) return
  const res = await call(
    () => crmApi.addDealItem(deal.value!.id, { product_id: newItem.product_id!, quantity: Number(newItem.quantity) || 1 }),
    'Не удалось добавить позицию.',
  )
  if (res === undefined) return
  newItem.product_id = null
  newItem.quantity = 1
  await loadItems()
  edit.amount = dealItems.total
}

const removeItem = async (itemId: number) => {
  if (!canUpdateDeal.value || !deal.value) return
  const res = await call(() => crmApi.deleteDealItem(deal.value!.id, itemId), 'Не удалось удалить позицию.')
  if (res === undefined) return
  await loadItems()
  if (dealItems.has_items) edit.amount = dealItems.total
}

onMounted(async () => {
  await Promise.all([
    loadDeal(),
    loadItems(),
    crmApi.listContacts().then(r => (contacts.value = r)),
    crmApi.listCompanies().then(r => (companies.value = r)),
    crmApi.listManagers().then(r => (managers.value = r)),
    crmApi.listProducts().then(r => (products.value = r)),
    crmApi.listTags().then(r => (allTags.value = r)).catch(() => { /* теги опциональны */ }),
  ])
  connectChatWs()
})

onUnmounted(() => {
  disconnectChatWs()
})

/* --- Actions --- */
const saveDealEdit = async () => {
  if (!canUpdateDeal.value || !deal.value || !edit.name) return
  const res = await call(
    () => crmApi.patchDeal(deal.value!.id, { ...edit, expected_close_date: edit.expected_close_date || null }),
    'Не удалось сохранить сделку.',
  )
  if (res === undefined) return
  await loadDeal()
}

const saveDealTags = async () => {
  if (!canUpdateDeal.value || !deal.value) return
  const res = await call(() => crmApi.setDealTags(deal.value!.id, dealTagIds.value), 'Не удалось сохранить теги.')
  if (res === undefined) return
  await loadDeal()
}

const removeDeal = async () => {
  if (!canDeleteDeal.value || !deal.value) return
  const res = await call(() => crmApi.deleteDeal(deal.value!.id), 'Не удалось удалить сделку.')
  if (res === undefined) return
  router.push('/app/deals')
}

const addNote = async () => {
  if (!canUpdateDeal.value || !deal.value || !newNote.value.trim()) return
  const dealId = deal.value.id
  const res = await call(
    () => crmApi.createActivity({ activity_type: newActivityType.value, deal_id: dealId, title: newNote.value }),
    'Не удалось добавить заметку.',
  )
  if (res === undefined) return
  newNote.value = ''
  newActivityType.value = 'note'
  await loadDeal()
}

const downloadPdf = (documentId: number) => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  window.open(`${apiUrl}/documents/${documentId}/pdf/?token=${getAccessToken()}&tenant_slug=${getTenantSlug()}`, '_blank')
}

const goBack = () => router.push('/app/deals')

/* --- Quick create --- */
const showQuickContact = ref(false)
const showQuickCompany = ref(false)
const quickCreateTarget = ref('')

const openQuickContact = () => { quickCreateTarget.value = 'deal-contact'; showQuickContact.value = true }
const openQuickCompany = () => { quickCreateTarget.value = 'deal-company'; showQuickCompany.value = true }

const onQuickContactCreated = async (res: { id: number }) => {
  const list = await call(() => crmApi.listContacts(), 'Не удалось создать контакт.')
  if (list !== undefined) contacts.value = list
  if (quickCreateTarget.value === 'deal-contact') edit.contact_id = res.id
}

const onQuickCompanyCreated = async (res: { id: number }) => {
  const list = await call(() => crmApi.listCompanies(), 'Не удалось создать компанию.')
  if (list !== undefined) companies.value = list
  if (quickCreateTarget.value === 'deal-company') edit.company_id = res.id
}

/* --- Chat --- */
const chatSessions = computed(() => deal.value?.chat_sessions || [])
const chatSessionOptions = computed(() =>
  chatSessions.value.map(s => ({
    label: `${s.channel_name || s.channel_type || 'Канал'} — ${s.external_user_name || s.external_chat_id || 'Неизвестно'}`,
    value: s.id,
  }))
)
const selectedChatSessionId = ref<number | null>(null)
const chatMessages = ref<any[]>([])
const chatMessageText = ref('')
const chatTabRef = ref<{ scrollToBottom: () => Promise<void> } | null>(null)

const activeChatSession = computed(() => chatSessions.value.find(s => s.id === selectedChatSessionId.value))

const loadChatMessages = async () => {
  const session = activeChatSession.value
  if (!session) { chatMessages.value = []; return }
  const channelId = session.channel_id
  const sessionId = session.id
  try {
    chatMessages.value = await api(`/channels/${channelId}/chats/${sessionId}/messages/`)
    await scrollToBottom()
  } catch {
    chatMessages.value = []
  }
}

watch(selectedChatSessionId, () => {
  chatMessages.value = []
  loadChatMessages()
})

const sendChatMessage = async () => {
  const text = chatMessageText.value.trim()
  const session = activeChatSession.value
  if (!text || !session) return
  chatMessageText.value = ''
  const tempId = -(Date.now())
  chatMessages.value.push({
    id: tempId, direction: 'out', text,
    attachments: [], external_message_id: '', crm_message_id: '',
    delivered: false, error: '', created_at: new Date().toISOString(),
  })
  await scrollToBottom()
  try {
    await api(`/channels/${session.channel_id}/send/`, {
      method: 'POST',
      body: { chat_session_id: session.id, text, attachments: [] },
    })
  } catch {
    // error will be shown when WS delivers real state or we could flag temp message
  }
}

const scrollToBottom = async () => {
  await chatTabRef.value?.scrollToBottom()
}

/* --- WS (chat) --- */
let chatSocket: WebSocket | null = null
let chatWsIntentionalClose = false
let chatWsRetryCount = 0
let chatWsRetryTimer: ReturnType<typeof setTimeout> | null = null

const scheduleChatWsReconnect = () => {
  if (chatWsRetryTimer || chatWsIntentionalClose) return
  const delay = Math.min(1000 * Math.pow(2, chatWsRetryCount), 30000)
  chatWsRetryCount++
  chatWsRetryTimer = setTimeout(() => {
    chatWsRetryTimer = null
    connectChatWs()
  }, delay)
}

const connectChatWs = async () => {
  disconnectChatWs()
  chatWsIntentionalClose = false
  let token = getAccessToken()
  if (!token) token = await refreshToken()
  const slug = getTenantSlug()
  if (!token || !slug) return
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  const wsBase = apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '')
  const ws = new WebSocket(`${wsBase}/ws/chat/?token=${token}&slug=${slug}`)

  ws.onopen = () => {
    chatSocket = ws
    chatWsRetryCount = 0
    // Subscribe to channel of active session if any
    const session = activeChatSession.value
    if (session) {
      ws.send(JSON.stringify({ action: 'subscribe', channel_id: session.channel_id }))
    }
  }

  ws.onclose = () => {
    chatSocket = null
    scheduleChatWsReconnect()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const session = activeChatSession.value
      if (!session) return
      if (data.type === 'chat.message' && data.session_id === session.id) {
        const real = data.message
        const existsIdx = chatMessages.value.findIndex((m: any) => m.id === real.id)
        if (existsIdx === -1) {
          const tempIdx = chatMessages.value.findIndex(
            (m: any) => m.id < 0 && m.direction === 'out' && m.text === real.text
          )
          if (tempIdx !== -1) {
            chatMessages.value.splice(tempIdx, 1, real)
          } else {
            chatMessages.value.push(real)
          }
          scrollToBottom()
        }
      }
      if (data.type === 'chat.session_update' && data.channel_id === session.channel_id) {
        // Refresh deal to get updated chat_sessions
        loadDeal()
      }
    } catch { /* ignore */ }
  }
}

const disconnectChatWs = () => {
  chatWsIntentionalClose = true
  if (chatWsRetryTimer) { clearTimeout(chatWsRetryTimer); chatWsRetryTimer = null }
  chatSocket?.close()
  chatSocket = null
  chatWsRetryCount = 0
}

watch(activeChatSession, (session) => {
  if (chatSocket && chatSocket.readyState === WebSocket.OPEN && session) {
    chatSocket.send(JSON.stringify({ action: 'subscribe', channel_id: session.channel_id }))
  }
})

/* --- Helpers --- */
const activityIcon = (type: string) => ({ call: '📞', message: '💬', task: '✅', note: '📝', email: '📧', document: '📄', stage_change: '🔄', system: '⚙️' }[type] || '📌')
const activityTypeLabel = (type: string) => ({ call: 'Звонок', message: 'Сообщение', task: 'Задача', note: 'Заметка', email: 'Email', document: 'Документ', stage_change: 'Смена стадии', system: 'Система' }[type] || type)
const documentStatusLabel = (s: string) => ({ draft: 'Черновик', sent: 'Отправлен', viewed: 'Просмотрен', signed: 'Подписан', expired: 'Истёк' }[s] || s)
</script>

<style scoped>
.view-gate,
:deep(.view-gate > div) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.deal-detail-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.deal-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.deal-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.deal-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 16px;
  overflow: auto;
}

.deal-tabs {
  display: flex;
  border-bottom: 2px solid var(--line);
  margin-bottom: 16px;
}

.deal-tab {
  padding: 10px 16px;
  border: none;
  background: transparent;
  font-family: 'Nunito Sans', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.15s;
}

.deal-tab.active {
  color: var(--brand);
  border-bottom-color: var(--brand);
}

.tab-pane {
  flex: 1;
}

.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
.select-with-add { display: flex; gap: 6px; align-items: flex-end; }
.flex-1 { flex: 1; }

.deal-tags-block { margin-top: 4px; }
.tag-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 8px; }
.tag-chip { display: inline-block; padding: 2px 10px; border-radius: 12px; color: #fff; font-size: 12px; font-weight: 600; }
.tags-empty { color: var(--text-muted); }

.status-badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.status-draft { background: var(--surface-alt); }
.status-sent { background: #dbeafe; color: #1d4ed8; }
.status-viewed { background: #fef3c7; color: #92400e; }
.status-signed { background: #dcfce7; color: #16a34a; }
.status-expired { background: #fee2e2; color: #991b1b; }

.activity-section { display: flex; flex-direction: column; gap: 8px; }
.activity-section h4 { margin: 0; font-size: 14px; }
.activity-list { max-height: 300px; overflow-y: auto; }
.timeline-item { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.tl-icon { font-size: 16px; flex-shrink: 0; }
.tl-content { flex: 1; min-width: 0; }
.tl-body { font-size: 13px; color: var(--text-muted); margin-top: 2px; }
.tl-meta { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.tl-date { font-size: 12px; color: var(--text-muted); }
.add-activity-row { display: flex; gap: 6px; }
.empty-state { color: var(--text-muted); padding: 24px; text-align: center; }

.items-section { display: flex; flex-direction: column; gap: 12px; }
.add-item-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.items-table { margin-top: 4px; }
.items-totals { display: flex; flex-direction: column; gap: 4px; align-items: flex-end; padding-top: 8px; border-top: 1px solid var(--line); }
.items-totals span { color: var(--text-muted); margin-right: 8px; }
.items-totals .grand { font-size: 15px; }
.amount-hint { color: var(--text-muted); font-size: 12px; }
</style>
