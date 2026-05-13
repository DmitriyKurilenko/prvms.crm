<template>
  <FeatureGate feature="messenger_channels">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Мессенджер-каналы</h1>
      </div>

      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <PButton label="Каналы" :outlined="activeTab !== 'channels'" @click="activeTab = 'channels'" size="small" />
        <PButton label="Чаты" :outlined="activeTab !== 'chats'" @click="activeTab = 'chats'; loadChatsTab()" size="small" />
      </div>

      <!-- ═══ CHANNELS TAB ═══ -->
      <template v-if="activeTab === 'channels'">
        <div class="surface-card" style="padding: 16px; margin-bottom: 12px">
          <h3 style="margin: 0 0 12px">{{ editingId ? 'Редактировать канал' : 'Подключить канал' }}</h3>
          <form @submit.prevent="submitChannel" style="display: flex; flex-direction: column; gap: 10px">
            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end">
              <div style="min-width: 200px">
                <label class="field-label">Название</label>
                <PInputText v-model="form.name" placeholder="Мой Telegram бот" style="width: 100%" />
              </div>
              <div style="min-width: 180px">
                <label class="field-label">Тип</label>
                <PSelect v-model="form.channel_type" :options="typeOptions" optionLabel="label" optionValue="value"
                  placeholder="Выберите тип" style="width: 100%" :disabled="!!editingId" />
              </div>
            </div>

            <!-- Dynamic credentials -->
            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end">
              <template v-if="form.channel_type === 'telegram'">
                <div style="min-width: 300px; flex: 1">
                  <label class="field-label">Bot Token</label>
                  <PInputText v-model="form.credentials.bot_token" placeholder="123456:ABC-DEF..." style="width: 100%" />
                </div>
              </template>
              <template v-if="form.channel_type === 'whatsapp' || form.channel_type === 'whatsapp_business'">
                <div style="min-width: 250px; flex: 1">
                  <label class="field-label">Send URL</label>
                  <PInputText v-model="form.credentials.send_url" placeholder="https://api.provider.com/send" style="width: 100%" />
                </div>
                <div style="min-width: 200px">
                  <label class="field-label">Auth Token</label>
                  <PInputText v-model="form.credentials.auth_token" placeholder="Bearer token" style="width: 100%" />
                </div>
              </template>
              <template v-if="form.channel_type === 'max'">
                <div style="min-width: 300px; flex: 1">
                  <label class="field-label">Bot Token</label>
                  <PInputText v-model="form.credentials.bot_token" placeholder="AAHdqTcvCH1vGWJx..." style="width: 100%" />
                </div>
              </template>
              <div style="min-width: 200px">
                <label class="field-label">Webhook Token (опц.)</label>
                <PInputText v-model="form.credentials.webhook_token" placeholder="Секрет для верификации" style="width: 100%" />
              </div>
            </div>

            <div style="display: flex; gap: 16px; flex-wrap: wrap; align-items: center">
              <label style="display: flex; align-items: center; gap: 6px; cursor: pointer">
                <input type="checkbox" v-model="form.auto_create_lead" />
                <span class="field-label" style="margin: 0">Создавать сделку при первом сообщении</span>
              </label>
            </div>

            <div>
              <label class="field-label">Приветственное сообщение (опц.)</label>
              <PTextarea v-model="form.welcome_message" rows="2" placeholder="Отправляется клиенту при первом обращении" style="width: 100%; max-width: 500px" />
            </div>

            <div style="display: flex; gap: 8px; align-items: center">
              <PButton type="submit" :label="editingId ? 'Сохранить' : 'Подключить'" :icon="editingId ? 'pi pi-check' : 'pi pi-plus'" />
              <PButton v-if="editingId" label="Отмена" text @click="cancelEdit" />
            </div>
          </form>
        </div>

        <div class="surface-card" style="padding: 16px">
          <PDataTable :value="channels" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
            <PColumn field="name" header="Название" />
            <PColumn header="Тип">
              <template #body="{ data }">{{ typeLabel(data.channel_type) }}</template>
            </PColumn>
            <PColumn header="Статус">
              <template #body="{ data }">
                <div style="display: flex; align-items: center; gap: 6px">
                  <PTag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" />
                  <span v-if="data.status_detail" style="font-size: 0.75em; color: var(--text-muted)" :title="data.status_detail">ⓘ</span>
                </div>
              </template>
            </PColumn>
            <PColumn header="Автолид">
              <template #body="{ data }">
                <span :style="{ color: data.auto_create_lead ? '#16a34a' : 'var(--text-muted)' }">{{ data.auto_create_lead ? 'Да' : 'Нет' }}</span>
              </template>
            </PColumn>
            <PColumn header="Webhook URL">
              <template #body="{ data }">
                <code style="font-size: 0.8em; word-break: break-all; cursor: pointer" @click="copyWebhook(data)" :title="'Нажмите чтобы скопировать'">
                  {{ webhookUrl(data) }}
                </code>
              </template>
            </PColumn>
            <PColumn header="Активен">
              <template #body="{ data }">
                <span :style="{ color: data.is_active ? '#059669' : '#dc2626' }">{{ data.is_active ? 'Да' : 'Нет' }}</span>
              </template>
            </PColumn>
            <PColumn header="">
              <template #body="{ data }">
                <PButton v-if="data.channel_type === 'telegram' || data.channel_type === 'max'" icon="pi pi-link" text size="small"
                  @click="registerWebhook(data.id)" title="Зарегистрировать webhook" :severity="data.status === 'error' ? 'danger' : 'secondary'" />
                <PButton icon="pi pi-pencil" text size="small" @click="startEdit(data)" />
                <PButton icon="pi pi-power-off" text size="small" :severity="data.is_active ? 'warning' : 'success'"
                  @click="toggleActive(data)" :title="data.is_active ? 'Деактивировать' : 'Активировать'" />
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeChannel(data.id)" />
              </template>
            </PColumn>
          </PDataTable>
        </div>
      </template>

      <!-- ═══ CHATS TAB ═══ -->
      <template v-if="activeTab === 'chats'">
        <div style="display: flex; gap: 12px; height: calc(100vh - 280px); min-height: 300px; max-height: 700px">
          <!-- Left: channel selector + sessions -->
          <div class="surface-card" style="width: 320px; min-width: 260px; padding: 12px; display: flex; flex-direction: column; overflow: hidden">
            <div style="margin-bottom: 10px">
              <label class="field-label">Канал</label>
              <PSelect v-model="selectedChannelId" :options="channelSelectOptions" optionLabel="label" optionValue="value"
                placeholder="Выберите канал" style="width: 100%" @change="loadSessions" />
            </div>
            <div style="flex: 1; overflow-y: auto">
              <div v-if="!sessions.length && selectedChannelId" style="color: var(--text-muted); padding: 12px">Нет чатов</div>
              <div v-for="s in sessions" :key="s.id"
                @click="selectSession(s)"
                :style="{
                  padding: '10px 8px', cursor: 'pointer', borderRadius: '6px',
                  background: activeSessionId === s.id ? 'var(--p-primary-50)' : 'transparent',
                  borderBottom: '1px solid var(--p-surface-200)'
                }">
                <div style="font-weight: 600; font-size: 0.9em">{{ s.external_user_name || s.external_chat_id }}</div>
                <div style="font-size: 0.75em; color: var(--text-muted)">
                  {{ formatDate(s.last_message_at) }}
                  <span v-if="s.crm_lead_id" style="margin-left: 6px">📋 Сделка #{{ s.crm_lead_id }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Right: messages -->
          <div class="surface-card" style="flex: 1; padding: 12px; display: flex; flex-direction: column; overflow: hidden">
            <template v-if="activeSessionId">
              <div style="font-weight: 600; margin-bottom: 8px; font-size: 0.9em; color: var(--text-muted)">
                {{ activeSessionName }}
              </div>
              <div ref="messagesContainer" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; padding: 4px">
                <div v-for="m in messages" :key="m.id"
                  :style="{
                    alignSelf: m.direction === 'out' ? 'flex-end' : 'flex-start',
                    maxWidth: '75%',
                    padding: '8px 12px',
                    borderRadius: '12px',
                    background: m.direction === 'out' ? 'var(--p-primary-100)' : 'var(--p-surface-100)',
                    fontSize: '0.9em'
                  }">
                  <div>{{ m.text }}</div>
                  <div style="font-size: 0.7em; color: var(--text-muted); text-align: right; margin-top: 2px">
                    {{ formatTime(m.created_at) }}
                    <span v-if="m.direction === 'out' && !m.delivered" style="color: #dc2626"> ✕</span>
                  </div>
                  <div v-if="m.error" style="font-size: 0.7em; color: #dc2626">{{ m.error }}</div>
                </div>
                <div v-if="!messages.length" style="color: var(--text-muted); padding: 20px; text-align: center">Нет сообщений</div>
              </div>
              <form @submit.prevent="sendMessage" style="display: flex; gap: 8px; margin-top: 8px">
                <PInputText v-model="messageText" placeholder="Написать ответ…" style="flex: 1" />
                <PButton type="button" icon="pi pi-comment" class="p-button-secondary" title="AI Ассистент" @click="openAIAssistant" :disabled="!activeSessionId" />
                <PButton type="submit" icon="pi pi-send" :disabled="!messageText.trim()" />
              </form>
            </template>
            <div v-else style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted)">
              Выберите чат
            </div>
          </div>
        </div>
      </template>
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import { refresh as refreshToken } from '@/api/auth'
import FeatureGate from '@/components/FeatureGate.vue'
import { formatDateTime, formatTime as fmtTime } from '@/utils/datetime'

const route = useRoute()
const toast = useToast()

/* ── state ── */
const activeTab = ref('channels')
const channels = ref<any[]>([])
const editingId = ref<number | null>(null)

const defaultForm = () => ({
  name: '',
  channel_type: 'telegram',
  credentials: { bot_token: '', send_url: '', auth_token: '', webhook_token: '' },
  auto_create_lead: true,
  welcome_message: '',
  is_active: true,
})
const form = reactive(defaultForm())

/* type options */
const typeOptions = [
  { value: 'telegram', label: 'Telegram Bot' },
  { value: 'whatsapp', label: 'WhatsApp (провайдер)' },
  { value: 'whatsapp_business', label: 'WhatsApp Business API' },
  { value: 'max', label: 'MAX' },
]
const typeLabel = (v: string) => typeOptions.find(o => o.value === v)?.label ?? v

const statusLabel = (s: string) => ({ active: 'Активен', error: 'Ошибка', disabled: 'Отключён' }[s] ?? s)
const statusSeverity = (s: string) => ({ active: 'success', error: 'danger', disabled: 'secondary' }[s] ?? 'info')

/* ── webhook URL helper ── */
const baseUrl = computed(() => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  return apiUrl.replace(/\/api\/?$/, '')
})
const webhookUrl = (ch: any) => `${baseUrl.value}/channels/webhook/${getTenantSlug() || 'unknown'}/${ch.channel_type}/${ch.id}/`
const copyWebhook = (ch: any) => {
  navigator.clipboard?.writeText(webhookUrl(ch))
}

/* ── channels CRUD ── */
const loadChannels = async () => {
  try {
    channels.value = await api('/channels/')
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить каналы.', life: 5000 })
  }
}

const submitChannel = async () => {
  if (!form.name.trim()) {
    toast.add({ severity: 'warn', summary: 'Заполните название', detail: 'Укажите название канала.', life: 4000 })
    return
  }
  if (form.channel_type === 'telegram' && !form.credentials.bot_token?.trim()) {
    toast.add({ severity: 'warn', summary: 'Укажите Bot Token', detail: 'Для Telegram необходимо указать Bot Token от @BotFather.', life: 5000 })
    return
  }
  if (form.channel_type === 'max' && !form.credentials.bot_token?.trim()) {
    toast.add({ severity: 'warn', summary: 'Укажите Bot Token', detail: 'Для MAX необходимо указать Bot Token.', life: 5000 })
    return
  }

  const body = {
    name: form.name,
    channel_type: form.channel_type,
    credentials: { ...form.credentials },
    auto_create_lead: form.auto_create_lead,
    welcome_message: form.welcome_message,
    is_active: form.is_active,
  }
  console.log('[Channels] submitChannel body:', JSON.stringify(body, null, 2))
  try {
    if (editingId.value) {
      await api(`/channels/${editingId.value}/`, { method: 'PATCH', body })
    } else {
      await api('/channels/', { method: 'POST', body })
    }
    cancelEdit()
    await loadChannels()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить канал.', life: 5000 })
  }
}

const startEdit = (ch: any) => {
  editingId.value = ch.id
  form.name = ch.name
  form.channel_type = ch.channel_type
  form.credentials = { ...(ch.credentials || {}) }
  form.auto_create_lead = ch.auto_create_lead
  form.welcome_message = ch.welcome_message || ''
  form.is_active = ch.is_active
}

const cancelEdit = () => {
  editingId.value = null
  Object.assign(form, defaultForm())
}

const toggleActive = async (ch: any) => {
  try {
    await api(`/channels/${ch.id}/`, { method: 'PATCH', body: { is_active: !ch.is_active } })
    await loadChannels()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось изменить статус канала.', life: 5000 })
  }
}

const removeChannel = async (id: number) => {
  try {
    await api(`/channels/${id}/`, { method: 'DELETE' })
    await loadChannels()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить канал.', life: 5000 })
  }
}

const registerWebhook = async (id: number) => {
  try {
    await api(`/channels/${id}/register-webhook/`, { method: 'POST' })
    await loadChannels()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось зарегистрировать webhook.', life: 5000 })
  }
}

/* ── chats ── */
const selectedChannelId = ref<number | null>(null)
const sessions = ref<any[]>([])
const activeSessionId = ref<number | null>(null)
const activeSessionName = ref('')
const messages = ref<any[]>([])
const messageText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const channelSelectOptions = computed(() =>
  channels.value.map(c => ({ value: c.id, label: `${c.name} (${typeLabel(c.channel_type)})` }))
)

const loadChatsTab = async () => {
  if (!channels.value.length) await loadChannels()
  if (!selectedChannelId.value && channels.value.length) {
    selectedChannelId.value = channels.value[0].id
  }
  if (selectedChannelId.value) await loadSessions()
}

const loadSessions = async () => {
  if (!selectedChannelId.value) { sessions.value = []; return }
  sessions.value = await api(`/channels/${selectedChannelId.value}/chats/`)
  // reset selected chat if channel changed
  if (activeSessionId.value) {
    const still = sessions.value.find((s: any) => s.id === activeSessionId.value)
    if (!still) { activeSessionId.value = null; messages.value = [] }
  }
}

const selectSession = async (s: any) => {
  activeSessionId.value = s.id
  activeSessionName.value = s.external_user_name || s.external_chat_id
  await loadMessages()
}

const loadMessages = async () => {
  if (!selectedChannelId.value || !activeSessionId.value) return
  messages.value = await api(`/channels/${selectedChannelId.value}/chats/${activeSessionId.value}/messages/`)
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const sendMessage = async () => {
  const text = messageText.value.trim()
  if (!text || !selectedChannelId.value || !activeSessionId.value) return

  if (text.startsWith('/ai ')) {
    const aiQuestion = text.slice(4).trim()
    if (aiQuestion) {
      messageText.value = ''
      await callAIAssistant(aiQuestion)
    }
    return
  }

  messageText.value = ''

  // Optimistic: show the message immediately before Celery processes it
  const tempId = -(Date.now())
  messages.value.push({
    id: tempId, direction: 'out', text,
    attachments: [], external_message_id: '', crm_message_id: '',
    delivered: false, error: '', created_at: new Date().toISOString(),
  })
  await nextTick()
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight

  await api(`/channels/${selectedChannelId.value}/send/`, {
    method: 'POST',
    body: { chat_session_id: activeSessionId.value, text, attachments: [] },
  })
  // When Celery broadcasts the real message via WS, deduplicate by removing the temp entry
  // (the onmessage handler skips messages already in the list by positive id)
}

/* ── date formatting ── */
const formatDate = (iso: string) => formatDateTime(iso, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', year: undefined })
const formatTime = (iso: string) => fmtTime(iso)

/* ── real-time WebSocket ── */
let chatSocket: WebSocket | null = null
let subscribedChannelId: number | null = null
let chatWsIntentionalClose = false
let chatWsRetryCount = 0
let chatWsRetryTimer: ReturnType<typeof setTimeout> | null = null

const scheduleChatWsReconnect = () => {
  if (chatWsRetryTimer || chatWsIntentionalClose) return
  const delay = Math.min(1000 * Math.pow(2, chatWsRetryCount), 30000)
  chatWsRetryCount++
  chatWsRetryTimer = setTimeout(() => {
    chatWsRetryTimer = null
    if (activeTab.value === 'chats') connectChatWs()
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
    // Subscribe to currently selected channel
    if (selectedChannelId.value) {
      ws.send(JSON.stringify({ action: 'subscribe', channel_id: selectedChannelId.value }))
      subscribedChannelId = selectedChannelId.value
    }
  }

  ws.onclose = () => {
    chatSocket = null
    subscribedChannelId = null
    scheduleChatWsReconnect()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'chat.message' && data.session_id === activeSessionId.value) {
        const real = data.message
        const existsIdx = messages.value.findIndex((m: any) => m.id === real.id)
        if (existsIdx === -1) {
          // Replace the most recent temp (negative id) outgoing message for this text, or append
          const tempIdx = messages.value.findIndex(
            (m: any) => m.id < 0 && m.direction === 'out' && m.text === real.text
          )
          if (tempIdx !== -1) {
            messages.value.splice(tempIdx, 1, real)
          } else {
            messages.value.push(real)
          }
          nextTick(() => {
            if (messagesContainer.value) {
              messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
            }
          })
        }
      }
      if (data.type === 'chat.session_update' && data.channel_id === selectedChannelId.value) {
        const idx = sessions.value.findIndex((s: any) => s.id === data.session.id)
        if (idx >= 0) {
          sessions.value[idx] = data.session
        } else {
          sessions.value.unshift(data.session)
        }
      }
    } catch { /* ignore */ }
  }
}

const disconnectChatWs = () => {
  chatWsIntentionalClose = true
  if (chatWsRetryTimer) { clearTimeout(chatWsRetryTimer); chatWsRetryTimer = null }
  chatSocket?.close()
  chatSocket = null
  subscribedChannelId = null
  chatWsRetryCount = 0
}

const wsSubscribeChannel = (channelId: number | null) => {
  if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) return
  // Unsubscribe from previous
  if (subscribedChannelId && subscribedChannelId !== channelId) {
    chatSocket.send(JSON.stringify({ action: 'unsubscribe', channel_id: subscribedChannelId }))
  }
  if (channelId) {
    chatSocket.send(JSON.stringify({ action: 'subscribe', channel_id: channelId }))
    subscribedChannelId = channelId
  }
}

watch(activeTab, (tab) => {
  if (tab === 'chats') connectChatWs()
  else disconnectChatWs()
})

watch(selectedChannelId, (id) => {
  wsSubscribeChannel(id)
})

/* ── init ── */
onMounted(async () => {
  await loadChannels()
  // Handle deep-link from deal detail: ?tab=chats&channel=ID&session=ID
  if (route.query.tab === 'chats') {
    activeTab.value = 'chats'
    if (route.query.channel) {
      selectedChannelId.value = Number(route.query.channel)
    }
    await loadChatsTab()
    if (route.query.session) {
      const sid = Number(route.query.session)
      const s = sessions.value.find((x: any) => x.id === sid)
      if (s) await selectSession(s)
    }
}
})

/* ── AI Assistant ── */
const callAIAssistant = async (question: string) => {
  const conversationId = activeSessionId.value ? await getOrCreateAIConversation() : null
  const context: Record<string, any> = {}
  if (activeSessionId.value) {
    context.channel_id = activeSessionId.value
  }
  if (sessions.value.find(s => s.id === activeSessionId.value)?.crm_lead_id) {
    context.deal_id = sessions.value.find(s => s.id === activeSessionId.value)?.crm_lead_id
  }

  const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:18100/api'}/ai/chat/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAccessToken()}`,
      'X-Tenant-Slug': getTenantSlug() || '',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      content: question,
      conversation_id: conversationId,
      ...context,
    }),
  })

  if (response.ok) {
    const result = await response.json()
    const tempId = -(Date.now())
    messages.value.push({
      id: tempId,
      direction: 'out',
      text: `[AI]: ${result.content}`,
      attachments: [],
      external_message_id: '',
      crm_message_id: '',
      delivered: true,
      error: '',
      created_at: new Date().toISOString(),
    })
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
}

const getOrCreateAIConversation = async (): Promise<number | null> => {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || 'http://localhost:18100/api'}/ai/conversations/`,
    { headers: { 'Authorization': `Bearer ${getAccessToken()}`, 'X-Tenant-Slug': getTenantSlug() || '' } }
  )
  if (response.ok) {
    const conversations = await response.json()
    const existing = conversations.find((c: any) => c.channel_id === activeSessionId.value)
    if (existing) return existing.id
  }
  return null
}

const openAIAssistant = () => {
  if (activeSessionId.value) {
    window.location.href = `/app/assistant?channel=${activeSessionId.value}`
  }
}

onUnmounted(disconnectChatWs)
</script>
