import { ref, type Ref } from 'vue'
import { Invitation, Inviter, Registerer, SessionState, UserAgent } from 'sip.js'
import type { Session } from 'sip.js'
import { getWebRTCCredentials } from '@/api/telephony'

export type SIPStatus = 'idle' | 'connecting' | 'ready' | 'calling' | 'incoming'

export interface IncomingCallInfo {
  callerNumber: string
  callerName: string
}

export function useSIPPhone(remoteAudioEl: Ref<HTMLAudioElement | null>) {
  const status = ref<SIPStatus>('idle')
  const extension = ref<string | null>(null)
  const incomingCall = ref<IncomingCallInfo | null>(null)
  const error = ref('')

  let ua: UserAgent | null = null
  let registerer: Registerer | null = null
  let currentSession: Session | null = null
  let incomingSession: Invitation | null = null
  let incomingRejectTimer: ReturnType<typeof setTimeout> | null = null

  // ---------------------------------------------------------------------------
  // Audio attachment
  // ---------------------------------------------------------------------------

  function _attachAudio(session: Session) {
    const sdh = session.sessionDescriptionHandler as any
    if (!sdh?.peerConnection) return
    sdh.peerConnection.addEventListener('track', (e: RTCTrackEvent) => {
      if (e.track.kind === 'audio' && remoteAudioEl.value && e.streams[0]) {
        remoteAudioEl.value.srcObject = e.streams[0]
        remoteAudioEl.value.play().catch(() => {})
      }
    })
  }

  // ---------------------------------------------------------------------------
  // Connect / Disconnect
  // ---------------------------------------------------------------------------

  const connect = async () => {
    error.value = ''
    status.value = 'connecting'
    try {
      const creds = await getWebRTCCredentials()
      if (!creds.extension || !creds.sip_password) {
        error.value = 'Для вашего аккаунта не настроен внутренний номер'
        status.value = 'idle'
        return
      }
      extension.value = creds.extension

      const wssUrl = creds.wss_url || 'wss://localhost:7443'
      // Use sip_domain when provided (per-tenant isolation), fall back to WSS hostname
      const sipDomain = (creds as any).sip_domain || new URL(wssUrl).hostname
      const uri = UserAgent.makeURI(`sip:${creds.extension}@${sipDomain}`)
      if (!uri) {
        error.value = 'Неверный SIP URI'
        status.value = 'idle'
        return
      }

      ua = new UserAgent({
        uri,
        authorizationPassword: creds.sip_password,
        authorizationUsername: creds.extension,
        transportOptions: { server: wssUrl },
        sessionDescriptionHandlerFactoryOptions: {
          constraints: { audio: true, video: false },
        },
        delegate: {
          onDisconnect: () => {
            status.value = 'idle'
          },
          onInvite: (invitation: Invitation) => {
            // Ignore if already in a call
            if (status.value === 'calling') {
              invitation.reject()
              return
            }
            incomingSession = invitation
            incomingCall.value = {
              callerNumber: invitation.request.from.uri.user ?? 'Неизвестный',
              callerName: invitation.request.from.displayName ?? '',
            }
            status.value = 'incoming'
            // Auto-reject after 30 seconds
            incomingRejectTimer = setTimeout(() => reject(), 30000)
          },
        },
      })

      await ua.start()
      registerer = new Registerer(ua)
      await registerer.register()
      status.value = 'ready'
    } catch (e) {
      error.value = `Ошибка подключения: ${e instanceof Error ? e.message : String(e)}`
      status.value = 'idle'
    }
  }

  const disconnect = async () => {
    if (registerer) await registerer.unregister().catch(() => {})
    if (ua) await ua.stop().catch(() => {})
    ua = null
    registerer = null
    currentSession = null
    incomingSession = null
    status.value = 'idle'
  }

  // ---------------------------------------------------------------------------
  // Outbound call
  // ---------------------------------------------------------------------------

  const makeCall = async (target: string) => {
    if (!ua || !target) return
    error.value = ''
    const host = ua.configuration.uri.host
    const targetUri = UserAgent.makeURI(`sip:${target}@${host}`)
    if (!targetUri) {
      error.value = 'Неверный номер'
      return
    }
    const inviter = new Inviter(ua, targetUri)
    currentSession = inviter
    inviter.stateChange.addListener((state: SessionState) => {
      if (state === SessionState.Established) {
        _attachAudio(inviter)
        status.value = 'calling'
      }
      if (state === SessionState.Terminated) {
        status.value = 'ready'
        currentSession = null
      }
    })
    status.value = 'calling'
    await inviter.invite()
  }

  // ---------------------------------------------------------------------------
  // Inbound call control
  // ---------------------------------------------------------------------------

  const answer = async () => {
    if (!incomingSession) return
    if (incomingRejectTimer) clearTimeout(incomingRejectTimer)
    const invitation = incomingSession
    currentSession = invitation
    incomingSession = null
    incomingCall.value = null
    try {
      await invitation.accept({
        sessionDescriptionHandlerOptions: {
          constraints: { audio: true, video: false },
        },
      })
      _attachAudio(invitation)
      status.value = 'calling'
    } catch (e) {
      error.value = `Ошибка ответа: ${e instanceof Error ? e.message : String(e)}`
      status.value = 'ready'
      currentSession = null
    }
  }

  const reject = () => {
    if (incomingRejectTimer) clearTimeout(incomingRejectTimer)
    if (incomingSession) {
      incomingSession.reject().catch(() => {})
      incomingSession = null
    }
    incomingCall.value = null
    status.value = status.value === 'incoming' ? 'ready' : status.value
  }

  // ---------------------------------------------------------------------------
  // Hangup
  // ---------------------------------------------------------------------------

  const hangup = () => {
    if (!currentSession) return
    const sess = currentSession
    currentSession = null
    if (sess instanceof Inviter) {
      if (sess.state === SessionState.Established) {
        sess.bye().catch(() => {})
      } else {
        sess.cancel().catch(() => {})
      }
    } else if (sess instanceof Invitation) {
      if (sess.state === SessionState.Established) {
        sess.bye().catch(() => {})
      } else {
        sess.reject().catch(() => {})
      }
    }
    status.value = 'ready'
  }

  // ---------------------------------------------------------------------------
  // DTMF
  // ---------------------------------------------------------------------------

  const sendDtmf = (digit: string) => {
    if (!currentSession || status.value !== 'calling') return
    currentSession
      .info({
        requestOptions: {
          body: {
            contentDisposition: 'render',
            contentType: 'application/dtmf-relay',
            content: `Signal=${digit}\r\nDuration=100`,
          },
        },
      })
      .catch(() => {})
  }

  return {
    status,
    extension,
    incomingCall,
    error,
    connect,
    disconnect,
    makeCall,
    answer,
    reject,
    hangup,
    sendDtmf,
  }
}
