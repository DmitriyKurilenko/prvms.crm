<template>
  <div v-if="visible" class="softphone">
    <!-- Панель раскрыта -->
    <div v-if="open || phone.status === 'incoming' || phone.status === 'in_call'" class="sp-panel" :class="{ 'sp-incoming': phone.status === 'incoming' }">
      <!-- Входящий звонок -->
      <template v-if="phone.status === 'incoming'">
        <p class="sp-label">Входящий звонок</p>
        <p class="sp-number">{{ phone.incomingFrom }}</p>
        <div class="sp-actions">
          <PButton label="Ответить" icon="pi pi-phone" severity="success" size="small" @click="phone.answer()" />
          <PButton label="Отклонить" icon="pi pi-phone-slash" severity="danger" size="small" @click="phone.decline()" />
        </div>
      </template>

      <!-- Активный звонок -->
      <template v-else-if="phone.status === 'in_call'">
        <p class="sp-label">{{ phone.activeDirection === 'inbound' ? 'Входящий' : 'Исходящий' }} · разговор</p>
        <p class="sp-number">{{ phone.activeNumber }}</p>
        <div class="sp-actions">
          <PButton :icon="phone.muted ? 'pi pi-microphone-slash' : 'pi pi-microphone'" :severity="phone.muted ? 'warning' : 'secondary'" size="small" rounded @click="phone.toggleMute()" />
          <PButton :icon="phone.held ? 'pi pi-play' : 'pi pi-pause'" severity="secondary" size="small" rounded @click="phone.toggleHold()" />
          <PButton icon="pi pi-phone-slash" severity="danger" size="small" rounded @click="phone.hangup()" />
        </div>
      </template>

      <!-- Готов: ручной набор -->
      <template v-else-if="phone.status === 'ready'">
        <p class="sp-label">Телефония · готов</p>
        <div class="sp-dial">
          <PInputText v-model="dialNumber" placeholder="Номер" class="w-full" @keyup.enter="dial" />
          <PButton icon="pi pi-phone" severity="success" size="small" :disabled="!dialNumber" @click="dial" />
        </div>
      </template>

      <!-- Подключение / ошибка / не подключён -->
      <template v-else>
        <p class="sp-label">Телефония · {{ statusLabel }}</p>
        <p v-if="phone.error" class="sp-error">{{ phone.error }}</p>
        <p v-else-if="phone.status === 'connecting'" class="sp-muted">Регистрируем софтфон…</p>
        <p v-else class="sp-muted">Софтфон не подключён.</p>
        <PButton v-if="phone.status !== 'connecting'" label="Подключить" icon="pi pi-refresh" size="small" outlined class="sp-retry" @click="reconnect" />
      </template>
    </div>

    <!-- Кнопка-лаунчер всегда видна -->
    <button class="sp-fab" :class="'st-' + phone.status" :title="statusLabel" @click="open = !open">
      <i class="pi pi-phone" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { usePhoneStore } from '@/stores/phone'

const phone = usePhoneStore()
const auth = useAuthStore()
const tenant = useTenantStore()
const { status } = storeToRefs(phone)

const open = ref(false)
const dialNumber = ref('')
let started = false

// Виджет виден всегда, когда у тенанта есть телефония — даже до регистрации,
// чтобы пользователь видел статус/ошибку и мог переподключиться.
const available = computed(() => auth.isAuthenticated && tenant.hasFeature('telephony'))
const visible = computed(() => available.value)

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    idle: 'Не подключён', connecting: 'Подключение…', ready: 'Готов',
    incoming: 'Входящий', in_call: 'Разговор', error: 'Ошибка',
  }
  return map[status.value] ?? status.value
})

function dial() {
  if (!dialNumber.value) return
  phone.call(dialNumber.value)
  dialNumber.value = ''
}

function reconnect() {
  phone.init().catch(() => {})
}

function startOnce() {
  // План (с фичами) грузится асинхронно после монтирования; запускаем регистрацию,
  // как только телефония становится доступна, ровно один раз.
  if (started || !available.value) return
  started = true
  phone.init().catch(() => {})
}

watch(available, startOnce, { immediate: true })
onMounted(startOnce)
</script>

<style scoped>
.softphone {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1200;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}
.sp-fab {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: none;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  box-shadow: var(--shadow, 0 4px 12px rgba(0,0,0,.2));
  background: var(--primary-color, #4f46e5);
}
.sp-fab.st-idle { background: #6b7280; }
.sp-fab.st-connecting { background: #d97706; }
.sp-fab.st-ready { background: #059669; }
.sp-fab.st-incoming { background: #3b82f6; animation: sp-pulse 1s infinite; }
.sp-fab.st-in_call { background: #dc2626; }
.sp-fab.st-error { background: #b91c1c; }
@keyframes sp-pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.08); } }
.sp-panel {
  width: 260px;
  padding: 14px;
  border-radius: 12px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--surface-border, #e5e7eb);
  box-shadow: var(--shadow, 0 8px 24px rgba(0,0,0,.18));
}
.sp-incoming { border-color: #bfdbfe; }
.sp-label { font-size: 12px; color: var(--text-muted, #6b7280); margin: 0 0 6px; font-weight: 600; }
.sp-number { font-size: 16px; font-weight: 700; margin: 0 0 10px; word-break: break-all; }
.sp-actions { display: flex; gap: 8px; }
.sp-dial { display: flex; gap: 8px; align-items: center; }
.sp-muted { font-size: 13px; color: var(--text-muted, #6b7280); margin: 0 0 8px; }
.sp-error { margin: 0 0 8px; color: #b91c1c; font-size: 12px; }
.sp-retry { width: 100%; }
</style>
