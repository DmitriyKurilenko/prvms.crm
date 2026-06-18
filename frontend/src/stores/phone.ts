import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  Communicator,
  RegistrationEvent,
  CallEvent,
  CallDirection,
  type Call,
} from '@exolve/web-voice-sdk'

import { clickToCall, clientLog, getWebRTCCredentials } from '@/api/telephony'
import { createLogger } from '@/utils/logger'

const log = createLogger('phone')

export type PhoneStatus = 'idle' | 'connecting' | 'ready' | 'incoming' | 'in_call' | 'error'

function onlyDigits(value: string): string {
  return (value || '').replace(/\D/g, '')
}

export const usePhoneStore = defineStore('phone', () => {
  const status = ref<PhoneStatus>('idle')
  const ready = ref(false)
  const error = ref('')
  const incomingFrom = ref('')
  const activeNumber = ref('')
  const activeDirection = ref<'inbound' | 'outbound'>('outbound')
  const muted = ref(false)
  const held = ref(false)

  let communicator: Communicator | null = null
  let current: Call | null = null

  function attachAudio(call: Call) {
    try {
      const el = call.audioElement
      if (el && !el.isConnected) {
        el.autoplay = true
        el.style.display = 'none'
        document.body.appendChild(el)
      }
    } catch { /* аудио-элемент необязателен для сигнализации */ }
  }

  function reset() {
    current = null
    incomingFrom.value = ''
    activeNumber.value = ''
    muted.value = false
    held.value = false
    status.value = ready.value ? 'ready' : 'idle'
  }

  /** Регистрация SIP-аккаунта менеджера в Exolve через официальный Web Voice SDK. */
  async function init(): Promise<boolean> {
    if (communicator) return ready.value
    status.value = 'connecting'
    error.value = ''
    let creds
    try {
      creds = await getWebRTCCredentials()
    } catch (e) {
      log.error('Не удалось получить SIP-креды', e)
      status.value = 'idle'
      return false
    }
    if (!creds.ready || !creds.username || !creds.password) {
      ready.value = false
      status.value = 'idle'
      return false
    }
    try {
      communicator = new Communicator()
      // enableSecureConnection=WSS; WSUrl/realm пакет берёт сам (корректный узел Exolve).
      await communicator.initialize({ enableSecureConnection: true, debug: true, maxLines: 2 })
      const client = communicator.client

      client.on(RegistrationEvent.Registered, () => {
        ready.value = true
        if (status.value === 'connecting') status.value = 'ready'
        clientLog('registered')
      })
      client.on(RegistrationEvent.Error, (e) => {
        ready.value = false
        error.value = e?.cause || 'Ошибка регистрации'
        status.value = 'error'
        clientLog('reg_error', `${e?.type ?? ''}:${e?.cause ?? ''}`)
      })

      client.on(CallEvent.New, (call) => {
        current = call
        attachAudio(call)
        if (call.direction === CallDirection.Incoming) {
          incomingFrom.value = call.number || 'Неизвестный'
          activeDirection.value = 'inbound'
          status.value = 'incoming'
          clientLog('incoming', call.number || '')
        } else {
          activeNumber.value = call.number
          activeDirection.value = 'outbound'
          status.value = 'in_call'
        }
      })
      client.on(CallEvent.Connected, (call) => {
        attachAudio(call)
        status.value = 'in_call'
        clientLog('call_connected')
      })
      client.on(CallEvent.OnHold, () => { held.value = true })
      client.on(CallEvent.Resumed, () => { held.value = false })
      client.on(CallEvent.Mute, (call) => { muted.value = call.isMuted })
      client.on(CallEvent.Error, (call, err) => {
        error.value = err?.cause || err?.type || 'Звонок не удался'
        clientLog('call_error', `${err?.type ?? ''}:${err?.cause ?? ''}`)
        reset()
      })
      client.on(CallEvent.Disconnected, () => {
        clientLog('call_disconnected')
        reset()
      })

      client.registerAccount(creds.username, creds.password)
      return true
    } catch (e) {
      log.error('Ошибка инициализации SIP', e)
      error.value = e instanceof Error && e.message ? e.message : 'Не удалось подключить телефонию'
      status.value = 'error'
      clientLog('init_error', error.value)
      return false
    }
  }

  async function call(number: string, ctx: { dealId?: number; contactId?: number } = {}) {
    const ok = communicator ? true : await init()
    if (!ok || !communicator) {
      error.value = 'Телефония не подключена'
      return
    }
    const target = onlyDigits(number)
    if (!target) return
    clickToCall({ to_number: target, deal_id: ctx.dealId, contact_id: ctx.contactId }).catch(() => {})
    activeNumber.value = number
    activeDirection.value = 'outbound'
    status.value = 'in_call'
    clientLog('call_start', target)
    try {
      communicator.client.makeCall(target)
    } catch (e) {
      log.error('Ошибка исходящего звонка', e)
      error.value = 'Звонок не удался'
      clientLog('call_outbound_error', e instanceof Error ? e.message : String(e))
      reset()
    }
  }

  function answer() {
    if (current) {
      current.accept()
      activeNumber.value = incomingFrom.value
      status.value = 'in_call'
    }
  }

  function decline() {
    if (current) current.terminate()
    reset()
  }

  function hangup() {
    if (current) current.terminate()
    reset()
  }

  function toggleMute() {
    if (!current) return
    muted.value ? current.unmute() : current.mute()
    muted.value = !muted.value
  }

  function toggleHold() {
    if (!current) return
    held.value ? current.resume() : current.hold()
    held.value = !held.value
  }

  function shutdown() {
    try {
      if (current) current.terminate()
      communicator?.client?.unregisterAccount()
    } catch { /* noop */ }
    communicator = null
    ready.value = false
    reset()
    status.value = 'idle'
  }

  return {
    status, ready, error, incomingFrom, activeNumber, activeDirection, muted, held,
    init, call, answer, decline, hangup, toggleMute, toggleHold, shutdown,
  }
})
