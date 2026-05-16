<template>
  <section class="assistant-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">AI Ассистент</h1>
    </div>

    <div class="assistant-layout">
      <!-- Conversations sidebar -->
      <div class="conversations-panel surface-card">
        <div class="conversations-header">
          <span class="section-title">Диалоги</span>
          <PButton icon="pi pi-plus" size="small" text @click="startNewConversation" />
        </div>

        <div v-if="aiStore.loading" class="loading-state">
          <span>Загрузка...</span>
        </div>

        <div v-else-if="aiStore.conversations.length === 0" class="empty-state">
          <p>Нет диалогов</p>
        </div>

        <div v-else class="conversations-list">
          <div
            v-for="conv in aiStore.conversations"
            :key="conv.id"
            class="conversation-item"
            :class="{ active: aiStore.activeConversation?.id === conv.id }"
            @click="selectConversation(conv)"
          >
            <div class="conv-title">{{ conv.title || 'Новый диалог' }}</div>
            <div class="conv-meta">{{ formatDate(conv.updated_at) }}</div>
            <button class="conv-delete" title="Удалить" @click.stop="deleteConversation(conv.id)">
              <i class="pi pi-trash" />
            </button>
          </div>
        </div>
      </div>

      <!-- Chat area -->
      <div class="chat-panel surface-card">
        <div v-if="!aiStore.activeConversation" class="empty-state">
          <i class="pi pi-comments" style="font-size: 48px; color: var(--text-muted)" />
          <p>Выберите диалог или начните новый</p>
          <PButton label="Начать новый диалог" icon="pi pi-plus" @click="startNewConversation" />
        </div>

        <template v-else>
          <div class="chat-messages" ref="messagesContainer">
            <div v-if="aiStore.messages.length === 0" class="empty-state">
              <p>Напишите сообщение ассистенту</p>
            </div>

            <div
              v-for="msg in aiStore.messages"
              :key="msg.id"
              class="message"
              :class="msg.role"
            >
              <div class="message-role">{{ msg.role === 'user' ? 'Вы' : 'AI' }}</div>
              <div class="message-content">{{ msg.content }}</div>
              <div class="message-time">{{ formatTime(msg.created_at) }}</div>
            </div>
          </div>

          <div class="chat-input">
            <PInputText
              v-model="inputText"
              placeholder="Напишите сообщение..."
              class="w-full"
              :disabled="aiStore.sending"
              @keydown.enter="sendMessage"
            />
            <PButton
              icon="pi pi-send"
              :disabled="!inputText.trim() || aiStore.sending"
              @click="sendMessage"
            />
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useAIStore, type AIConversation } from '@/stores/ai'

const aiStore = useAIStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

onMounted(async () => {
  await aiStore.loadConversations()
  await aiStore.connect()
})

onUnmounted(() => {
  aiStore.disconnect()
})

function startNewConversation() {
  aiStore.setActiveConversation(null)
  inputText.value = ''
}

function selectConversation(conv: AIConversation) {
  aiStore.setActiveConversation(conv)
}

async function sendMessage() {
  if (!inputText.value.trim() || aiStore.sending) return

  const text = inputText.value.trim()
  inputText.value = ''

  const conversationId = aiStore.activeConversation?.id
  await aiStore.sendMessage(text, conversationId)

  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function deleteConversation(id: number) {
  if (confirm('Удалить диалог?')) {
    await aiStore.deleteConversation(id)
  }
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.assistant-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
}

.assistant-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

@media (max-width: 768px) {
  .assistant-layout {
    grid-template-columns: 1fr;
  }
  /* Keep the chat reachable: cap the conversation list height on phones */
  .conversations-panel {
    max-height: 38vh;
  }
}

.conversations-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.conversations-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--surface-border);
}

.conversations-list {
  flex: 1;
  overflow-y: auto;
}

.conversation-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--surface-border);
  position: relative;
  transition: background 0.2s;
}

.conversation-item:hover {
  background: var(--surface-hover);
}

.conversation-item.active {
  background: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 15%, transparent);
}

.conv-title {
  font-weight: 500;
  margin-bottom: 4px;
  padding-right: 24px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.conv-delete {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  padding: 4px;
}

.conversation-item:hover .conv-delete {
  opacity: 1;
}

.conv-delete:hover {
  color: var(--red-500);
}

.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  padding: 12px 16px;
  border-radius: 8px;
  max-width: 80%;
}

.message.user {
  background: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  align-self: flex-end;
}

.message.assistant {
  background: var(--surface-ground);
  align-self: flex-start;
}

.message-role {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.message-content {
  line-height: 1.5;
  white-space: pre-wrap;
}

.message-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
  text-align: right;
}

.chat-input {
  display: flex;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid var(--surface-border);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  gap: 12px;
}

.loading-state {
  padding: 16px;
  text-align: center;
  color: var(--text-muted);
}
</style>