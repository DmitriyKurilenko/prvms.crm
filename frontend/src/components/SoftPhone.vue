<template>
  <div class="surface-card phone">
    <h4>WebRTC Софтфон</h4>
    <p>Статус: <strong :class="'st-' + phone.status.value">{{ statusLabel }}</strong></p>
    <p v-if="phone.extension.value" style="font-size: 13px; color: var(--text-muted)">Внутренний: {{ phone.extension.value }}</p>

    <div v-if="phone.status.value === 'idle'">
      <PButton label="Подключиться" icon="pi pi-wifi" @click="phone.connect()" />
    </div>

    <div v-if="phone.status.value === 'incoming'" class="incoming-block">
      <p class="incoming-label">Входящий звонок</p>
      <p class="incoming-number">{{ phone.incomingCall.value?.callerNumber }}<span v-if="phone.incomingCall.value?.callerName"> · {{ phone.incomingCall.value.callerName }}</span></p>
      <div class="actions">
        <PButton label="Ответить" icon="pi pi-phone" severity="success" @click="phone.answer()" />
        <PButton label="Отклонить" icon="pi pi-phone-slash" severity="danger" @click="phone.reject()" />
      </div>
    </div>

    <div v-if="phone.status.value === 'ready' || phone.status.value === 'calling'" style="margin-top: 10px">
      <PInputText v-model="target" placeholder="Номер" style="width: 100%; margin-bottom: 8px" :disabled="phone.status.value === 'calling'" />
      <div class="actions">
        <PButton label="Позвонить" icon="pi pi-phone" @click="phone.makeCall(target)" :disabled="phone.status.value === 'calling' || !target" />
        <PButton severity="danger" label="Завершить" icon="pi pi-phone-slash" @click="phone.hangup()" :disabled="phone.status.value !== 'calling'" />
      </div>
    </div>

    <div v-if="phone.status.value === 'calling'" class="dtmf-block" style="margin-top: 10px">
      <PInputText v-model="dtmfDigit" placeholder="#" maxlength="1" style="width: 60px; margin-right: 8px" />
      <PButton label="DTMF" icon="pi pi-hashtag" severity="secondary" size="small" @click="sendDtmf" :disabled="!dtmfDigit" />
    </div>

    <div v-if="phone.error.value" class="error-msg">{{ phone.error.value }}</div>

    <audio ref="audioEl" autoplay style="display: none" />
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useSIPPhone } from '@/composables/useSIPPhone'

const audioEl = ref<HTMLAudioElement | null>(null)
const phone = useSIPPhone(audioEl)

const target = ref('')
const dtmfDigit = ref('')

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    idle: 'Отключён',
    connecting: 'Подключение...',
    ready: 'Готов',
    calling: 'Звонок...',
    incoming: 'Входящий звонок',
  }
  return map[phone.status.value] ?? phone.status.value
})

const sendDtmf = () => {
  if (!dtmfDigit.value) return
  phone.sendDtmf(dtmfDigit.value)
  dtmfDigit.value = ''
}

onUnmounted(() => {
  phone.disconnect()
})
</script>

<style scoped>
.phone {
  padding: 14px;
}

.actions {
  display: flex;
  gap: 8px;
}

.incoming-block {
  margin-top: 10px;
  padding: 10px;
  background: #eff6ff;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
}

.incoming-label {
  font-size: 12px;
  color: #3b82f6;
  margin: 0 0 4px;
  font-weight: 600;
}

.incoming-number {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 8px;
}

.dtmf-block {
  display: flex;
  align-items: center;
}

.st-idle { color: var(--text-muted); }
.st-connecting { color: #d97706; }
.st-ready { color: #059669; }
.st-calling { color: #dc2626; }
.st-incoming { color: #3b82f6; }

.error-msg {
  margin-top: 8px;
  padding: 8px;
  background: #fee2e2;
  border-radius: 8px;
  color: #991b1b;
  font-size: 13px;
}
</style>
