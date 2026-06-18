<template>
  <section class="notifications-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Уведомления</h1>
    </div>

    <!-- In-app история -->
    <div class="surface-card notif-card">
      <div class="notif-card-header">
        <h3>История уведомлений</h3>
        <PButton v-if="canManage" label="Тест" icon="pi pi-send" size="small" @click="sendTest" />
      </div>
      <PDataTable v-responsive-table :value="items" :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
        <PColumn field="title" header="Заголовок" />
        <PColumn field="body" header="Текст" />
        <PColumn field="sent_at" header="Дата" />
      </PDataTable>
    </div>

    <!-- Настройки уведомлений (owner/admin) -->
    <div v-if="canManage" class="surface-card notif-card">
      <h3 style="margin-bottom: 12px">Настройки уведомлений</h3>
      <p style="color: var(--text-muted); margin-bottom: 16px; font-size: 0.9rem">
        Выберите, какие события и по каким каналам получать уведомления.
      </p>
      <PDataTable v-responsive-table :value="eventRows" :loading="prefsLoading">
        <PColumn field="label" header="Событие" style="min-width: 200px" />
        <PColumn header="In-app" style="width: 100px; text-align: center">
          <template #body="{ data }">
            <PToggleSwitch
              :modelValue="isPrefEnabled(data.event, 'in_app')"
              @update:modelValue="togglePref(data.event, 'in_app', $event)"
            />
          </template>
        </PColumn>
        <PColumn header="Email" style="width: 100px; text-align: center">
          <template #body="{ data }">
            <PToggleSwitch
              :modelValue="isPrefEnabled(data.event, 'email')"
              @update:modelValue="togglePref(data.event, 'email', $event)"
            />
          </template>
        </PColumn>
        <PColumn header="Telegram" style="width: 100px; text-align: center">
          <template #body="{ data }">
            <PToggleSwitch
              :modelValue="isPrefEnabled(data.event, 'telegram')"
              @update:modelValue="togglePref(data.event, 'telegram', $event)"
            />
          </template>
        </PColumn>
      </PDataTable>
    </div>

    <!-- Telegram-привязка -->
    <div class="surface-card notif-card">
      <h3 style="margin-bottom: 12px">Telegram-уведомления</h3>

      <div v-if="tgLoading" style="color: var(--text-muted)">Загрузка...</div>

      <template v-else>
        <div v-if="tgStatus?.linked" class="tg-linked">
          <span class="tg-linked-text">
            <i class="pi pi-check-circle" />
            Привязан: @{{ tgStatus.username || tgStatus.chat_id }}
          </span>
          <PButton label="Отвязать" icon="pi pi-times" severity="secondary" size="small" @click="handleUnlink" />
        </div>

        <div v-else>
          <p style="color: var(--text-muted); margin-bottom: 12px; font-size: 0.9rem">
            Привяжите Telegram-аккаунт, чтобы получать уведомления в мессенджере.
          </p>
          <div v-if="tgLinkUrl" class="tg-link-box">
            <p style="margin-bottom: 8px; font-size: 0.9rem">
              Перейдите по ссылке и нажмите <strong>Запустить</strong> в боте:
            </p>
            <a :href="tgLinkUrl" target="_blank" rel="noopener" class="tg-link-url">
              {{ tgLinkUrl }}
            </a>
            <p style="margin-top: 8px; font-size: 0.85rem; color: var(--text-muted)">
              Ссылка действует 10 минут. После привязки обновите страницу.
            </p>
          </div>
          <PButton
            label="Привязать Telegram"
            icon="pi pi-send"
            size="small"
            :loading="tgLinking"
            @click="handleLink"
          />
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useNotifications } from '@/composables/useNotifications'
import { useToast } from 'primevue/usetoast'
import { useAuthStore } from '@/stores/auth'
import {
  listPreferences,
  updatePreferences,
  telegramStatus,
  linkTelegramInit,
  unlinkTelegram,
  type NotificationPreference,
  type TelegramStatus,
} from '@/api/notifications'

const { items, load, notifications } = useNotifications()
const auth = useAuthStore()
const toast = useToast()

const canManage = computed(() => auth.role === 'owner' || auth.role === 'admin')

const sendTest = async () => notifications.sendTest()

// --- Preferences matrix ---
const EVENTS: { event: string; label: string }[] = [
  { event: 'document_signed', label: 'Документ подписан' },
  { event: 'lead_distributed', label: 'Заявка распределена' },
  { event: 'task_overdue', label: 'Просроченная задача' },
  { event: 'new_deal_created', label: 'Создана новая сделка' },
  { event: 'plan_limit_warning', label: 'Лимиты плана близки к исчерпанию' },
  { event: 'plan_limit_reached', label: 'Лимит плана достигнут' },
  { event: 'crm_connection_lost', label: 'Потеряно соединение с CRM' },
  { event: 'crm_connection_restored', label: 'Соединение с CRM восстановлено' },
  { event: 'user_invited', label: 'Пользователь приглашён' },
  { event: 'manager_sync_done', label: 'Синхронизация менеджеров завершена' },
  { event: 'signing_expired', label: 'Срок подписания истёк' },
  { event: 'deal_stage_changed', label: 'Сделка перемещена' },
]

const eventRows = EVENTS

const prefs = ref<NotificationPreference[]>([])
const prefsLoading = ref(false)

function isPrefEnabled(event: string, channel: string): boolean {
  const found = prefs.value.find(p => p.event === event && p.channel === channel)
  return found ? found.is_enabled : false
}

async function togglePref(event: string, channel: string, enabled: boolean) {
  const existing = prefs.value.find(p => p.event === event && p.channel === channel)
  if (existing) {
    existing.is_enabled = enabled
  } else {
    prefs.value.push({ event, channel, is_enabled: enabled, recipient_roles: ['owner', 'admin'] })
  }
  await updatePreferences([{ event, channel, is_enabled: enabled, recipient_roles: existing?.recipient_roles ?? ['owner', 'admin'] }])
}

async function loadPrefs() {
  if (!canManage.value) return
  prefsLoading.value = true
  try {
    prefs.value = await listPreferences()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить настройки уведомлений.', life: 5000 })
  } finally {
    prefsLoading.value = false
  }
}

// --- Telegram ---
const tgStatus = ref<TelegramStatus | null>(null)
const tgLoading = ref(false)
const tgLinking = ref(false)
const tgLinkUrl = ref('')

async function loadTgStatus() {
  tgLoading.value = true
  try {
    tgStatus.value = await telegramStatus()
  } catch {
    tgStatus.value = null
  } finally {
    tgLoading.value = false
  }
}

async function handleLink() {
  tgLinking.value = true
  try {
    const result = await linkTelegramInit()
    if (result.telegram_link) {
      tgLinkUrl.value = result.telegram_link
      window.open(result.telegram_link, '_blank', 'noopener')
    } else {
      tgLinkUrl.value = ''
      alert('Настройте TELEGRAM_NOTIFICATION_BOT_USERNAME на сервере для генерации ссылки.')
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось инициировать привязку Telegram.', life: 5000 })
  } finally {
    tgLinking.value = false
  }
}

async function handleUnlink() {
  await unlinkTelegram()
  tgStatus.value = null
  tgLinkUrl.value = ''
  await loadTgStatus()
}

onMounted(async () => {
  await Promise.all([load(), loadPrefs(), loadTgStatus()])
})
</script>

<style scoped>
.notifications-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.notif-card {
  padding: 16px;
}

.notif-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tg-linked {
  display: flex;
  align-items: center;
  gap: 16px;
}

.tg-linked-text {
  color: #16a34a;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tg-link-box {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
}

.tg-link-url {
  word-break: break-all;
  color: var(--brand);
}
</style>
