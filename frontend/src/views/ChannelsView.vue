<template>
  <FeatureGate feature="messenger_channels">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Мессенджер-каналы</h1>
      </div>

      <div style="display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap">
        <PButton label="Каналы" :outlined="activeTab !== 'channels'" @click="activeTab = 'channels'" size="small" />
        <PButton label="Чаты" :outlined="activeTab !== 'chats'" @click="activeTab = 'chats'; loadChatsTab()" size="small" />
        <div style="flex: 1"></div>
        <PButton label="Подключить ВКонтакте" icon="pi pi-external-link" size="small" @click="connectVk" />
      </div>

      <!-- ═══ CHANNELS TAB ═══ -->
      <ChannelsTab
        v-if="activeTab === 'channels'"
        :form="form"
        :editing-id="editingId"
        :channels="channels"
        :type-options="typeOptions"
        :type-label="typeLabel"
        :status-label="statusLabel"
        :status-severity="statusSeverity"
        :webhook-url="webhookUrl"
        @submit="submitChannel"
        @cancel="cancelEdit"
        @edit="startEdit"
        @toggle="toggleActive"
        @remove="removeChannel"
        @register-webhook="registerWebhook"
        @copy-webhook="copyWebhook"
      />

      <!-- ═══ CHATS TAB ═══ -->
      <ChatsTab
        v-if="activeTab === 'chats'"
        ref="chatsTab"
        v-model:selected-channel-id="selectedChannelId"
        v-model:message-text="messageText"
        :channel-select-options="channelSelectOptions"
        :sessions="sessions"
        :active-session-id="activeSessionId"
        :active-session-name="activeSessionName"
        :messages="messages"
        @channel-change="loadSessions"
        @select-session="selectSession"
        @send-message="sendMessage"
        @open-a-i-assistant="openAIAssistant"
      />
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import { refresh as refreshToken } from '@/api/auth'
import { startVkOauth } from '@/api/channels'
import FeatureGate from '@/components/FeatureGate.vue'
import ChannelsTab from '@/components/ChannelsTab.vue'
import ChatsTab from '@/components/ChatsTab.vue'

const route = useRoute()
const toast = useToast()

/* ── state ── */
const activeTab = ref('channels')
const channels = ref<any[]>([])
const editingId = ref<number | null>(null)

const defaultForm = () => ({
  name: '',
  channel_type: 'telegram',
  credentials: {
    bot_token: '', send_url: '', auth_token: '', webhook_token: '',
    imap_host: '', imap_port: 993, imap_ssl: true,
    smtp_host: '', smtp_port: 465, smtp_ssl: true,
    username: '', password: '', poll_folder: 'INBOX', from_name: '',
  },
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
  { value: 'vk', label: 'ВКонтакте' },
  { value: 'email', label: 'Электронная почта' },
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

const connectVk = async () => {
  try {
    const { authorize_url, state } = await startVkOauth()
    sessionStorage.setItem('vk_oauth_state', state)
    window.location.href = authorize_url
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось начать подключение ВКонтакте.', life: 5000 })
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
  if (form.channel_type === 'email') {
    const c = form.credentials
    if (!c.imap_host?.trim() || !c.smtp_host?.trim() || !c.username?.trim() || !c.password?.trim()) {
      toast.add({ severity: 'warn', summary: 'Заполните настройки почты', detail: 'Укажите IMAP-хост, SMTP-хост, логин и пароль.', life: 5000 })
      return
    }
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
const chatsTab = ref<InstanceType<typeof ChatsTab> | null>(null)

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
  await chatsTab.value?.scrollToBottom()
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
  await chatsTab.value?.scrollToBottom()

  await api(`/channels/${selectedChannelId.value}/send/`, {
    method: 'POST',
    body: { chat_session_id: activeSessionId.value, text, attachments: [] },
  })
  // When Celery broadcasts the real message via WS, deduplicate by removing the temp entry
  // (the onmessage handler skips messages already in the list by positive id)
}


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
          chatsTab.value?.scrollToBottom()
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
    await chatsTab.value?.scrollToBottom()
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
