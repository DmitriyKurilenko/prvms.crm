<template>
  <FeatureGate feature="messenger_channels">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Мессенджер-каналы</h1>
      </div>

      <div style="display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap">
        <div style="flex: 1"></div>
        <PButton label="Подключить ВКонтакте" icon="pi pi-external-link" size="small" @click="connectVk" />
      </div>

      <ChannelsTab
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
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { api, getTenantSlug } from '@/api/http'
import { startVkOauth } from '@/api/channels'
import FeatureGate from '@/components/FeatureGate.vue'
import ChannelsTab from '@/components/ChannelsTab.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()

/* ── state ── */
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

/* ── init ── */
onMounted(async () => {
  // Переписка перенесена в самостоятельный раздел «Чаты» (/app/chats).
  // Старые ссылки на вкладку чатов внутри каналов перенаправляем туда.
  if (route.query.tab === 'chats') {
    router.replace('/app/chats')
    return
  }
  await loadChannels()
})
</script>
