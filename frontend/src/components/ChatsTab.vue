<template>
  <div style="display: flex; gap: 12px; height: calc(100vh - 280px); min-height: 300px; max-height: 700px">
    <!-- Left: channel selector + sessions -->
    <div class="surface-card" style="width: 320px; min-width: 260px; padding: 12px; display: flex; flex-direction: column; overflow: hidden">
      <div style="margin-bottom: 10px">
        <label class="field-label">Канал</label>
        <PSelect
          :modelValue="selectedChannelId"
          @update:modelValue="$emit('update:selectedChannelId', $event)"
          @change="$emit('channelChange')"
          :options="channelSelectOptions"
          optionLabel="label"
          optionValue="value"
          placeholder="Выберите канал"
          style="width: 100%"
        />
      </div>
      <div style="flex: 1; overflow-y: auto">
        <div v-if="!sessions.length && selectedChannelId" style="color: var(--text-muted); padding: 12px">Нет чатов</div>
        <div v-for="s in sessions" :key="s.id"
          @click="$emit('selectSession', s)"
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
        <form @submit.prevent="$emit('sendMessage')" style="display: flex; gap: 8px; margin-top: 8px">
          <PInputText
            :modelValue="messageText"
            @update:modelValue="$emit('update:messageText', $event ?? '')"
            placeholder="Написать ответ…"
            style="flex: 1"
          />
          <PButton type="button" icon="pi pi-comment" class="p-button-secondary" title="AI Ассистент" @click="$emit('openAIAssistant')" :disabled="!activeSessionId" />
          <PButton type="submit" icon="pi pi-send" :disabled="!messageText.trim()" />
        </form>
      </template>
      <div v-else style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted)">
        Выберите чат
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { formatDateTime, formatTime as fmtTime } from '@/utils/datetime'

/**
 * Presentational shell for the Chats tab. All chat state, the WebSocket
 * lifecycle and send/load logic stay in the parent. This component only
 * owns the scroll container DOM node and exposes `scrollToBottom()` so
 * the parent's WS/send/load handlers keep deciding *when* to scroll —
 * a 1:1 control-flow-preserving relocation (no scroll heuristic).
 */
defineProps<{
  channelSelectOptions: { value: number; label: string }[]
  selectedChannelId: number | null
  sessions: any[]
  activeSessionId: number | null
  activeSessionName: string
  messages: any[]
  messageText: string
}>()

defineEmits<{
  'update:selectedChannelId': [number | null]
  'update:messageText': [string]
  channelChange: []
  selectSession: [any]
  sendMessage: []
  openAIAssistant: []
}>()

const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatDate = (iso: string) => formatDateTime(iso, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', year: undefined })
const formatTime = (iso: string) => fmtTime(iso)

defineExpose({ scrollToBottom })
</script>

<style scoped>
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
</style>
