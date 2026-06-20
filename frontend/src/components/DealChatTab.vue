<template>
  <div v-if="sessions.length" class="chat-pane">
    <div class="chat-channel-select">
      <label class="field-label">Канал общения</label>
      <PSelect
        :modelValue="selectedSessionId"
        @update:modelValue="$emit('update:selectedSessionId', $event)"
        :options="sessionOptions"
        optionLabel="label"
        optionValue="value"
        placeholder="Выберите канал"
        style="width: 100%"
      />
    </div>
    <template v-if="selectedSessionId">
      <div ref="messagesContainer" class="chat-messages">
        <div v-for="m in messages" :key="m.id" :class="['chat-bubble', m.direction === 'out' ? 'chat-out' : 'chat-in']">
          <div>{{ m.text }}</div>
          <div class="chat-meta">
            {{ formatTime(m.created_at) }}
            <span v-if="m.direction === 'out' && !m.delivered" style="color: #dc2626"> ✕</span>
          </div>
          <div v-if="m.error" class="chat-error">{{ m.error }}</div>
        </div>
        <div v-if="!messages.length" class="empty-state">Нет сообщений</div>
      </div>
      <form v-if="canSend" @submit.prevent="$emit('sendMessage')" class="chat-input-row">
        <PInputText
          :modelValue="messageText"
          @update:modelValue="$emit('update:messageText', $event ?? '')"
          placeholder="Написать ответ…"
          style="flex: 1"
        />
        <PButton type="submit" icon="pi pi-send" :disabled="!messageText.trim()" />
      </form>
    </template>
    <div v-else class="empty-state">Выберите канал общения</div>
  </div>
  <div v-else class="empty-state">Нет привязанных каналов общения</div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { formatTime } from '@/utils/datetime'

/**
 * Презентационная оболочка вкладки «Чат» сделки. Всё состояние чата,
 * жизненный цикл WebSocket и логика send/load остаются в родителе
 * (DealDetailView). Компонент владеет только DOM-узлом прокрутки и
 * экспонирует scrollToBottom() — родитель решает, *когда* прокручивать,
 * как и в ChatsTab.vue (DEC-036). Перенос 1:1, без scroll-эвристики.
 */
defineProps<{
  sessions: any[]
  sessionOptions: { value: number; label: string }[]
  selectedSessionId: number | null
  messages: any[]
  messageText: string
  canSend: boolean
}>()

defineEmits<{
  'update:selectedSessionId': [number | null]
  'update:messageText': [string]
  sendMessage: []
}>()

const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

defineExpose({ scrollToBottom })
</script>

<style scoped>
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.empty-state { color: var(--text-muted); padding: 24px; text-align: center; }

.chat-pane { display: flex; flex-direction: column; gap: 10px; height: 100%; }
.chat-channel-select { flex-shrink: 0; }
.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
}
.chat-bubble {
  max-width: 75%;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 0.9em;
}
.chat-in {
  align-self: flex-start;
  background: var(--p-surface-100);
}
.chat-out {
  align-self: flex-end;
  background: var(--p-primary-100);
}
.chat-meta {
  font-size: 0.7em;
  color: var(--text-muted);
  text-align: right;
  margin-top: 2px;
}
.chat-error {
  font-size: 0.7em;
  color: #dc2626;
}
.chat-input-row {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
</style>
