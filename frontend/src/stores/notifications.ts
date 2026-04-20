import { defineStore } from 'pinia'
import { listNotifications, markAllRead, markRead, sendTestNotification, type UiNotification } from '@/api/notifications'
import { getAccessToken, getTenantSlug } from '@/api/http'
import { refresh } from '@/api/auth'

interface NotificationsState {
  items: UiNotification[]
  connected: boolean
  socket: WebSocket | null
  _retryTimer: ReturnType<typeof setTimeout> | null
  _retryCount: number
  _intentionalClose: boolean
  _connecting: boolean
}

export const useNotificationsStore = defineStore('notifications', {
  state: (): NotificationsState => ({
    items: [],
    connected: false,
    socket: null,
    _retryTimer: null,
    _retryCount: 0,
    _intentionalClose: false,
    _connecting: false,
  }),
  getters: {
    unreadCount: (state) => state.items.filter((item) => !item.is_read).length
  },
  actions: {
    async load() {
      this.items = await listNotifications()
    },

    async connect() {
      if (this.socket || this._connecting) return
      this._connecting = true

      // Always refresh the token before connecting to ensure it's valid
      let token = await refresh()
      if (!token) {
        token = getAccessToken()
      }
      if (!token) {
        console.warn('[notifications] no token, cannot connect WS')
        this._connecting = false
        return
      }

      this._intentionalClose = false
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
      const wsBase = apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '')
      const slug = getTenantSlug()
      const params = new URLSearchParams({ token })
      if (slug) params.set('slug', slug)
      const wsUrl = `${wsBase}/ws/notifications/?${params.toString()}`
      console.log('[notifications] connecting WS:', wsBase + '/ws/notifications/')

      const socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        console.log('[notifications] WS connected')
        const isReconnect = this._retryCount > 0
        this.connected = true
        this._retryCount = 0
        // Reload on reconnect to catch notifications missed while disconnected
        if (isReconnect) {
          this.load()
        }
      }

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          console.log('[notifications] WS message:', payload)
          if (payload.id) {
            this.items = [payload, ...this.items]
          }
        } catch {
          // ignore malformed messages
        }
      }

      socket.onclose = (evt) => {
        console.log('[notifications] WS closed, code:', evt.code)
        this.connected = false
        this.socket = null
        if (!this._intentionalClose) {
          this._scheduleReconnect()
        }
      }

      socket.onerror = (err) => {
        console.error('[notifications] WS error', err)
        // onclose fires after onerror, reconnect handled there
      }

      this.socket = socket
      this._connecting = false
    },

    _scheduleReconnect() {
      if (this._retryTimer) return
      // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
      const delay = Math.min(1000 * Math.pow(2, this._retryCount), 30000)
      this._retryCount++
      console.log(`[notifications] reconnecting in ${delay}ms (attempt ${this._retryCount})`)
      this._retryTimer = setTimeout(async () => {
        this._retryTimer = null
        await this.connect()
      }, delay)
    },

    disconnect() {
      this._intentionalClose = true
      this._connecting = false
      if (this._retryTimer) {
        clearTimeout(this._retryTimer)
        this._retryTimer = null
      }
      this.socket?.close()
      this.socket = null
      this.connected = false
      this._retryCount = 0
    },

    async read(id: number) {
      await markRead(id)
      const item = this.items.find((entry) => entry.id === id)
      if (item) {
        item.is_read = true
      }
    },

    async readAll() {
      await markAllRead()
      this.items = this.items.map((item) => ({ ...item, is_read: true }))
    },

    async sendTest() {
      await sendTestNotification()
    }
  }
})
