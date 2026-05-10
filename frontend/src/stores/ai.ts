import { defineStore } from 'pinia'
import { getAccessToken, getTenantSlug } from '@/api/http'
import { refresh } from '@/api/auth'

export interface AIMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export interface AIConversation {
  id: number
  title: string
  channel_id: number | null
  deal_id: number | null
  created_at: string
  updated_at: string
  message_count: number
}

interface AIState {
  conversations: AIConversation[]
  activeConversation: AIConversation | null
  messages: AIMessage[]
  loading: boolean
  sending: boolean
  socket: WebSocket | null
  connected: boolean
  _retryTimer: ReturnType<typeof setTimeout> | null
  _retryCount: number
  _intentionalClose: boolean
  _connecting: boolean
}

export const useAIStore = defineStore('ai', {
  state: (): AIState => ({
    conversations: [],
    activeConversation: null,
    messages: [],
    loading: false,
    sending: false,
    socket: null,
    connected: false,
    _retryTimer: null,
    _retryCount: 0,
    _intentionalClose: false,
    _connecting: false,
  }),

  actions: {
    async loadConversations() {
      this.loading = true
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/ai/conversations/`, {
          headers: {
            'Authorization': `Bearer ${getAccessToken()}`,
            'X-Tenant-Slug': getTenantSlug() || '',
          },
        })
        if (response.ok) {
          this.conversations = await response.json()
        }
      } finally {
        this.loading = false
      }
    },

    async loadMessages(conversationId: number) {
      this.loading = true
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL}/ai/conversations/${conversationId}/messages/`,
          {
            headers: {
              'Authorization': `Bearer ${getAccessToken()}`,
              'X-Tenant-Slug': getTenantSlug() || '',
            },
          }
        )
        if (response.ok) {
          this.messages = await response.json()
        }
      } finally {
        this.loading = false
      }
    },

    async sendMessage(content: string, conversationId?: number, context?: Record<string, any>) {
      this.sending = true
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/ai/chat/`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${getAccessToken()}`,
            'X-Tenant-Slug': getTenantSlug() || '',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content,
            conversation_id: conversationId,
            ...context,
          }),
        })
        if (response.ok) {
          const result = await response.json()
          this.messages.push({
            id: result.message_id,
            role: 'assistant',
            content: result.content,
            created_at: new Date().toISOString(),
          })
          return result
        }
      } finally {
        this.sending = false
      }
    },

    async deleteConversation(conversationId: number) {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/ai/conversations/${conversationId}/`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${getAccessToken()}`,
            'X-Tenant-Slug': getTenantSlug() || '',
          },
        }
      )
      if (response.ok) {
        this.conversations = this.conversations.filter((c) => c.id !== conversationId)
        if (this.activeConversation?.id === conversationId) {
          this.activeConversation = null
          this.messages = []
        }
      }
    },

    async updateTitle(conversationId: number, title: string) {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/ai/conversations/${conversationId}/title/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${getAccessToken()}`,
            'X-Tenant-Slug': getTenantSlug() || '',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ title }),
        }
      )
      if (response.ok) {
        const conv = this.conversations.find((c) => c.id === conversationId)
        if (conv) {
          conv.title = title
        }
        if (this.activeConversation?.id === conversationId) {
          this.activeConversation.title = title
        }
      }
    },

    async connect() {
      if (this.socket || this._connecting) return
      this._connecting = true

      let token = await refresh()
      if (!token) {
        token = getAccessToken()
      }
      if (!token) {
        console.warn('[ai] no token, cannot connect WS')
        this._connecting = false
        return
      }

      this._intentionalClose = false
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
      const wsBase = apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '')
      const slug = getTenantSlug()
      const params = new URLSearchParams({ token })
      if (slug) params.set('slug', slug)
      const wsUrl = `${wsBase}/ws/ai/?${params.toString()}`

      const socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        console.log('[ai] WS connected')
        this.connected = true
        this._retryCount = 0
      }

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'ai_response') {
            this.messages.push({
              id: payload.message_id,
              role: 'assistant',
              content: payload.content,
              created_at: new Date().toISOString(),
            })
          }
        } catch {
          // ignore
        }
      }

      socket.onclose = (evt) => {
        this.connected = false
        this.socket = null
        if (!this._intentionalClose) {
          this._scheduleReconnect()
        }
      }

      this.socket = socket
      this._connecting = false
    },

    _scheduleReconnect() {
      if (this._retryTimer) return
      const delay = Math.min(1000 * Math.pow(2, this._retryCount), 30000)
      this._retryCount++
      this._retryTimer = setTimeout(() => {
        this._retryTimer = null
        this.connect()
      }, delay)
    },

    disconnect() {
      this._intentionalClose = true
      if (this._retryTimer) {
        clearTimeout(this._retryTimer)
        this._retryTimer = null
      }
      this.socket?.close()
      this.socket = null
      this.connected = false
      this._retryCount = 0
    },

    setActiveConversation(conv: AIConversation | null) {
      this.activeConversation = conv
      if (conv) {
        this.loadMessages(conv.id)
      } else {
        this.messages = []
      }
    },
  },
})