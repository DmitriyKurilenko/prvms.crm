<template>
  <FeatureGate feature="telephony">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Телефония</h1>
      </div>

      <div class="tabs-bar">
        <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <!-- CALLS TAB -->
      <div v-if="tab === 'calls'" class="tab-content">
        <div class="stats-row" v-if="stats">
          <div class="stat-card surface-card"><strong>{{ stats.total }}</strong><span>Всего</span></div>
          <div class="stat-card surface-card"><strong>{{ stats.missed }}</strong><span>Пропущено</span></div>
          <div class="stat-card surface-card"><strong>{{ Math.round(stats.avg_duration) }}с</strong><span>Ср. длительность</span></div>
        </div>

        <!-- Фильтры (п.46) -->
        <div class="filter-bar surface-card">
          <select v-model="filters.direction" class="select-sm" style="width: 140px">
            <option value="">Все направления</option>
            <option value="inbound">Входящие</option>
            <option value="outbound">Исходящие</option>
          </select>
          <select v-model="filters.result" class="select-sm" style="width: 160px">
            <option value="">Все результаты</option>
            <option value="answered">Отвечен</option>
            <option value="missed">Пропущен</option>
            <option value="busy">Занято</option>
            <option value="voicemail">Голос. почта</option>
            <option value="ivr_only">IVR</option>
          </select>
          <input type="date" v-model="filters.date_from" class="select-sm" style="width: 150px" />
          <input type="date" v-model="filters.date_to" class="select-sm" style="width: 150px" />
          <PButton label="Применить" size="small" @click="loadCalls" />
          <PButton label="Сбросить" size="small" severity="secondary" @click="resetFilters" />
        </div>

        <PDataTable :value="calls" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="direction" header="Направление" style="width: 120px">
            <template #body="{ data }">{{ data.direction === 'inbound' ? '📞 Входящий' : '📤 Исходящий' }}</template>
          </PColumn>
          <PColumn field="caller_number" header="От" />
          <PColumn field="called_number" header="Кому" />
          <PColumn field="result" header="Результат" style="width: 130px">
            <template #body="{ data }">
              <span :class="'result-' + data.result">{{ resultLabel(data.result) }}</span>
            </template>
          </PColumn>
          <PColumn field="duration" header="Длит." style="width: 90px">
            <template #body="{ data }">{{ formatDuration(data.duration) }}</template>
          </PColumn>
          <PColumn field="manager_name" header="Менеджер" />
          <PColumn field="started_at" header="Время" style="width: 140px">
            <template #body="{ data }">{{ formatDateTime(data.started_at) }}</template>
          </PColumn>
          <!-- Запись (п.47) -->
          <PColumn header="Запись" style="width: 80px">
            <template #body="{ data }">
              <PButton v-if="data.record_file" icon="pi pi-play" text size="small" @click="openPlayer(data)" title="Прослушать запись" />
            </template>
          </PColumn>
          <!-- Click-to-call (п.49) -->
          <PColumn header="" style="width: 50px">
            <template #body="{ data }">
              <PButton icon="pi pi-phone" text size="small" @click="openOriginate(data.caller_number)" title="Позвонить" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- TRUNKS TAB -->
      <div v-if="tab === 'trunks'" class="tab-content">
        <div class="toolbar">
          <PButton label="Новый транк" icon="pi pi-plus" size="small" @click="showTrunkForm = true" />
        </div>
        <PDataTable :value="trunks" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="name" header="Название" />
          <PColumn field="trunk_type" header="Тип" />
          <PColumn field="status" header="Статус">
            <template #body="{ data }">
              <span :class="'trunk-status-' + data.status">{{ data.status }}</span>
            </template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <PButton icon="pi pi-check-circle" text size="small" @click="testTrunkAction(data.id)" title="Тест" />
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeTrunk(data.id)" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- EXTENSIONS TAB -->
      <div v-if="tab === 'extensions'" class="tab-content">
        <div class="toolbar">
          <PButton label="Новый внутренний" icon="pi pi-plus" size="small" @click="showExtForm = true" />
        </div>
        <PDataTable :value="extensions" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="extension" header="Номер" />
          <PColumn field="manager_id" header="Менеджер ID" />
          <PColumn field="webrtc_enabled" header="WebRTC">
            <template #body="{ data }">{{ data.webrtc_enabled ? 'Да' : 'Нет' }}</template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeExtension(data.id)" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- IVR TAB -->
      <div v-if="tab === 'ivr'" class="tab-content">
        <div class="toolbar">
          <PButton label="Новое IVR" icon="pi pi-plus" size="small" @click="showIvrForm = true" />
        </div>
        <div v-for="ivr in ivrs" :key="ivr.id" class="surface-card ivr-card">
          <div class="ivr-header">
            <strong>{{ ivr.name }}</strong>
            <div>
              <PButton icon="pi pi-pencil" text size="small" @click="editIvr(ivr)" />
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeIvr(ivr.id)" />
            </div>
          </div>
          <div class="ivr-rules">
            <div v-for="(opt, i) in ivr.options" :key="i" class="ivr-rule">
              <span class="ivr-digit">{{ opt.digit }}</span>
              <span class="ivr-arrow">→</span>
              <span class="ivr-action">{{ formatIvrAction(opt.action) }}</span>
            </div>
            <span v-if="!ivr.options.length" class="text-muted">Нет правил</span>
          </div>
          <div class="ivr-meta">Таймаут: {{ ivr.timeout }}с</div>
        </div>
      </div>

      <!-- QUEUES TAB -->
      <div v-if="tab === 'queues'" class="tab-content">
        <div class="toolbar">
          <PButton label="Новая очередь" icon="pi pi-plus" size="small" @click="showQueueForm = true" />
        </div>
        <PDataTable :value="queues" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="name" header="Название" />
          <PColumn field="strategy" header="Стратегия" />
          <PColumn field="ring_timeout" header="Таймаут (с)" />
          <PColumn header="Участники">
            <template #body="{ data }">{{ data.members.length }}</template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeQueue(data.id)" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- SOFTPHONE TAB -->
      <div v-if="tab === 'phone'" class="tab-content">
        <SoftPhone />
      </div>

      <!-- TRUNK FORM -->
      <PDialog v-model:visible="showTrunkForm" header="SIP Транк" :style="{ width: '450px' }" modal>
        <div class="form-grid">
          <PInputText v-model="trunkForm.name" placeholder="Название" />
          <select v-model="trunkForm.trunk_type" class="select-sm">
            <option value="zadarma">Zadarma</option>
            <option value="mcn">MCN Telecom</option>
            <option value="rostelecom">Ростелеком</option>
            <option value="exolve">МТС Exolve</option>
            <option value="custom_sip">Произвольный SIP</option>
          </select>
          <PInputText v-model="trunkForm.username" :placeholder="trunkForm.trunk_type === 'exolve' ? 'SIP User (числовой ID из кабинета Exolve)' : 'SIP User'" />
          <PInputText v-model="trunkForm.password" placeholder="SIP Password" type="password" />
          <PInputText v-model="trunkForm.proxy" placeholder="SIP Proxy (sip.provider.com)" />
          <PButton label="Создать" @click="submitTrunk" />
        </div>
      </PDialog>

      <!-- EXTENSION FORM -->
      <PDialog v-model:visible="showExtForm" header="Внутренний номер" :style="{ width: '400px' }" modal>
        <div class="form-grid">
          <PInputText v-model.number="extForm.manager_id" placeholder="ID менеджера" type="number" />
          <PInputText v-model="extForm.extension" placeholder="Номер (100, 101...)" />
          <PInputText v-model="extForm.sip_password" placeholder="SIP пароль" type="password" />
          <PButton label="Создать" @click="submitExtension" />
        </div>
      </PDialog>

      <!-- IVR FORM -->
      <PDialog v-model:visible="showIvrForm" header="IVR Menu" :style="{ width: '520px' }" modal>
        <div class="form-grid">
          <PInputText v-model="ivrForm.name" placeholder="Название" />
          <PInputText v-model="ivrForm.greeting_tts" placeholder="Приветственное сообщение (TTS)" />
          <div class="ivr-rules-editor">
            <div class="ivr-rules-header">
              <span>Правила меню</span>
              <PButton label="+ Правило" text size="small" @click="ivrForm.options.push({ digit: '', action: '', actionType: '', actionTarget: '' })" />
            </div>
            <div v-for="(opt, idx) in ivrForm.options" :key="idx" class="ivr-rule-row">
              <span class="ivr-rule-label">Нажать</span>
              <PInputText v-model="opt.digit" placeholder="0–9, *" style="width: 60px" />
              <span class="ivr-rule-label">→ Действие</span>
              <select v-model="opt.actionType" class="select-sm" style="width: 150px" @change="opt.action = opt.actionType + ':'">
                <option value="queue">Очередь</option>
                <option value="extension">Номер</option>
                <option value="ivr">IVR</option>
                <option value="hangup">Завершить</option>
              </select>
              <PInputText v-if="opt.actionType !== 'hangup'" v-model="opt.actionTarget" :placeholder="actionPlaceholder(opt.actionType)" style="flex: 1" @input="opt.action = opt.actionType + ':' + opt.actionTarget" />
              <PButton icon="pi pi-minus" text size="small" severity="danger" @click="ivrForm.options.splice(idx, 1)" />
            </div>
            <p v-if="!ivrForm.options.length" class="text-muted" style="font-size: 13px; margin: 4px 0">Нет правил — добавьте хотя бы одно</p>
          </div>
          <PInputText v-model.number="ivrForm.timeout" placeholder="Таймаут (сек)" type="number" />
          <PButton :label="ivrForm.id ? 'Сохранить' : 'Создать'" @click="submitIvr" />
        </div>
      </PDialog>

      <!-- QUEUE FORM -->
      <PDialog v-model:visible="showQueueForm" header="Очередь звонков" :style="{ width: '450px' }" modal>
        <div class="form-grid">
          <PInputText v-model="queueForm.name" placeholder="Название" />
          <select v-model="queueForm.strategy" class="select-sm">
            <option value="ring_all">Звонок всем</option>
            <option value="round_robin">По очереди</option>
            <option value="least_recent">Наименее недавний</option>
            <option value="random">Случайный</option>
          </select>
          <PInputText v-model.number="queueForm.ring_timeout" placeholder="Таймаут звонка (сек)" type="number" />
          <PButton label="Создать" @click="submitQueue" />
        </div>
      </PDialog>

      <!-- AUDIO PLAYER DIALOG (п.47) -->
      <PDialog v-model:visible="showPlayer" header="Запись разговора" :style="{ width: '420px' }" modal @hide="stopAudio">
        <div v-if="playerCall" style="display: flex; flex-direction: column; gap: 12px">
          <div style="font-size: 13px; color: var(--text-muted)">
            {{ playerCall.caller_number }} → {{ playerCall.called_number }} &nbsp;|&nbsp; {{ formatDateTime(playerCall.started_at) }}
          </div>
          <audio ref="audioEl" :src="playerCall.record_file ?? undefined" controls style="width: 100%; outline: none" preload="metadata" />
          <a :href="playerCall.record_file ?? undefined" download class="download-link">
            <i class="pi pi-download" style="margin-right: 4px" />Скачать запись
          </a>
        </div>
      </PDialog>

      <!-- ORIGINATE DIALOG (п.49) -->
      <PDialog v-model:visible="showOriginate" header="Click-to-call" :style="{ width: '380px' }" modal>
        <div class="form-grid">
          <div style="font-size: 13px; color: var(--text-muted)">Набрать номер через FreeSWITCH</div>
          <PInputText v-model="originateForm.to_number" placeholder="Номер назначения" />
          <PInputText v-model="originateForm.from_number" placeholder="Ваш номер / внутренний" />
          <PButton label="Позвонить" icon="pi pi-phone" :loading="originateLoading" @click="doOriginate" />
          <p v-if="originateError" style="color: #dc2626; font-size: 13px">{{ originateError }}</p>
          <p v-if="originateOk" style="color: #059669; font-size: 13px">Звонок инициирован</p>
        </div>
      </PDialog>
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import FeatureGate from '@/components/FeatureGate.vue'
import SoftPhone from '@/components/SoftPhone.vue'
import * as telApi from '@/api/telephony'
import type { CallFilters, CallRecord, CallQueue, Extension, IvrMenu, Trunk } from '@/api/telephony'
import { formatDateTime } from '@/utils/datetime'

const tabs = [
  { key: 'calls', label: 'Звонки' },
  { key: 'trunks', label: 'Транки' },
  { key: 'extensions', label: 'Внутренние' },
  { key: 'ivr', label: 'IVR' },
  { key: 'queues', label: 'Очереди' },
  { key: 'phone', label: 'Софтфон' },
]
const tab = ref('calls')

/* --- Calls + filters (п.46) --- */
const calls = ref<CallRecord[]>([])
const stats = ref<{ total: number; missed: number; avg_duration: number } | null>(null)
const filters = reactive<CallFilters>({ result: '', direction: '', date_from: '', date_to: '' })

const loadCalls = async () => {
  const f: CallFilters = {}
  if (filters.result) f.result = filters.result
  if (filters.direction) f.direction = filters.direction
  if (filters.date_from) f.date_from = filters.date_from
  if (filters.date_to) f.date_to = filters.date_to
  calls.value = await telApi.listCalls(f)
  stats.value = await telApi.callStats()
}

const resetFilters = async () => {
  filters.result = ''
  filters.direction = ''
  filters.date_from = ''
  filters.date_to = ''
  await loadCalls()
}

const resultLabel = (r: string) => {
  const map: Record<string, string> = { answered: 'Отвечен', missed: 'Пропущен', busy: 'Занято', voicemail: 'Голос. почта', ivr_only: 'IVR' }
  return map[r] || r
}

const formatDuration = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return m > 0 ? `${m}м ${sec}с` : `${sec}с`
}

/* --- Audio player (п.47) --- */
const showPlayer = ref(false)
const playerCall = ref<CallRecord | null>(null)
const audioEl = ref<HTMLAudioElement | null>(null)

const openPlayer = (call: CallRecord) => {
  playerCall.value = call
  showPlayer.value = true
}

const stopAudio = () => {
  audioEl.value?.pause()
}

/* --- Click-to-call (п.49) --- */
const showOriginate = ref(false)
const originateForm = reactive({ to_number: '', from_number: '' })
const originateLoading = ref(false)
const originateError = ref('')
const originateOk = ref(false)

const openOriginate = (number: string) => {
  originateForm.to_number = number
  originateForm.from_number = ''
  originateError.value = ''
  originateOk.value = false
  showOriginate.value = true
}

const doOriginate = async () => {
  if (!originateForm.to_number) return
  originateLoading.value = true
  originateError.value = ''
  originateOk.value = false
  try {
    await telApi.originate({ from_number: originateForm.from_number, to_number: originateForm.to_number })
    originateOk.value = true
    await loadCalls()
  } catch {
    originateError.value = 'Не удалось соединиться с сервером телефонии'
  } finally {
    originateLoading.value = false
  }
}

/* --- Trunks --- */
const trunks = ref<Trunk[]>([])
const showTrunkForm = ref(false)
const trunkForm = reactive({ name: '', trunk_type: 'custom_sip', username: '', password: '', proxy: '' })

watch(() => trunkForm.trunk_type, (type) => {
  if (type === 'exolve' && !trunkForm.proxy) {
    trunkForm.proxy = 'sip.exolve.ru'
  }
})

const loadTrunks = async () => { trunks.value = await telApi.listTrunks() }

const submitTrunk = async () => {
  await telApi.createTrunk({
    name: trunkForm.name,
    trunk_type: trunkForm.trunk_type,
    credentials: { username: trunkForm.username, password: trunkForm.password, proxy: trunkForm.proxy },
  })
  showTrunkForm.value = false
  trunkForm.name = ''
  trunkForm.username = ''
  trunkForm.password = ''
  trunkForm.proxy = ''
  await loadTrunks()
}

const testTrunkAction = async (id: number) => {
  await telApi.testTrunk(id)
  await loadTrunks()
}

const removeTrunk = async (id: number) => {
  await telApi.deleteTrunk(id)
  await loadTrunks()
}

/* --- Extensions --- */
const extensions = ref<Extension[]>([])
const showExtForm = ref(false)
const extForm = reactive({ manager_id: null as number | null, extension: '', sip_password: '' })

const loadExtensions = async () => { extensions.value = await telApi.listExtensions() }

const submitExtension = async () => {
  if (!extForm.manager_id || !extForm.extension) return
  await telApi.createExtension(extForm)
  showExtForm.value = false
  extForm.manager_id = null
  extForm.extension = ''
  extForm.sip_password = ''
  await loadExtensions()
}

const removeExtension = async (id: number) => {
  await telApi.deleteExtension(id)
  await loadExtensions()
}

/* --- IVR (п.44) --- */
interface IvrOption { digit: string; action: string; actionType: string; actionTarget: string }

const ivrs = ref<IvrMenu[]>([])
const showIvrForm = ref(false)
const ivrForm = reactive({
  id: null as number | null,
  name: '',
  greeting_tts: '',
  timeout: 10,
  options: [] as IvrOption[],
})

const actionPlaceholder = (type: string) => {
  if (type === 'queue') return 'Название очереди'
  if (type === 'extension') return 'Номер (101)'
  if (type === 'ivr') return 'Название IVR'
  return ''
}

const formatIvrAction = (action: string) => {
  if (!action) return '—'
  const [type, target] = action.split(':')
  const labels: Record<string, string> = { queue: 'Очередь', extension: 'Номер', ivr: 'IVR', hangup: 'Завершить' }
  return target ? `${labels[type] ?? type}: ${target}` : (labels[type] ?? action)
}

const loadIvrs = async () => { ivrs.value = await telApi.listIvr() }

const editIvr = (ivr: IvrMenu) => {
  ivrForm.id = ivr.id
  ivrForm.name = ivr.name
  ivrForm.timeout = ivr.timeout
  ivrForm.options = ivr.options.map(o => {
    const [type, target] = (o.action || '').split(':')
    return { digit: o.digit, action: o.action, actionType: type || 'queue', actionTarget: target || '' }
  })
  showIvrForm.value = true
}

const submitIvr = async () => {
  if (!ivrForm.name) return
  const options = ivrForm.options.map(o => ({ digit: o.digit, action: o.action }))
  const data = { name: ivrForm.name, greeting_tts: ivrForm.greeting_tts, options, timeout: ivrForm.timeout }
  if (ivrForm.id) {
    await telApi.patchIvr(ivrForm.id, data)
  } else {
    await telApi.createIvr(data)
  }
  showIvrForm.value = false
  ivrForm.id = null
  ivrForm.name = ''
  ivrForm.greeting_tts = ''
  ivrForm.timeout = 10
  ivrForm.options = []
  await loadIvrs()
}

const removeIvr = async (id: number) => {
  await telApi.deleteIvr(id)
  await loadIvrs()
}

/* --- Queues --- */
const queues = ref<CallQueue[]>([])
const showQueueForm = ref(false)
const queueForm = reactive({ name: '', strategy: 'ring_all', ring_timeout: 20 })

const loadQueues = async () => { queues.value = await telApi.listQueues() }

const submitQueue = async () => {
  if (!queueForm.name) return
  await telApi.createQueue(queueForm)
  showQueueForm.value = false
  queueForm.name = ''
  queueForm.strategy = 'ring_all'
  queueForm.ring_timeout = 20
  await loadQueues()
}

const removeQueue = async (id: number) => {
  await telApi.deleteQueue(id)
  await loadQueues()
}

/* --- Init --- */
onMounted(async () => {
  await Promise.all([loadCalls(), loadTrunks(), loadExtensions(), loadIvrs(), loadQueues()])
})
</script>

<style scoped>
.tabs-bar { display: flex; gap: 4px; margin-bottom: 14px; flex-wrap: wrap; }
.tab-btn { padding: 8px 16px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); cursor: pointer; font-size: 14px; }
.tab-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
.tab-content { min-height: 300px; }
.toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.select-sm { padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); font-size: 14px; }
.form-grid { display: grid; gap: 10px; }
.stats-row { display: flex; gap: 12px; margin-bottom: 14px; }
.stat-card { padding: 14px; text-align: center; flex: 1; }
.stat-card strong { display: block; font-size: 24px; }
.stat-card span { font-size: 13px; color: var(--text-muted); }

.filter-bar { display: flex; gap: 8px; align-items: center; padding: 10px 12px; margin-bottom: 12px; flex-wrap: wrap; }

.trunk-status-active { color: #059669; font-weight: 600; }
.trunk-status-error { color: #dc2626; font-weight: 600; }
.trunk-status-registering { color: #d97706; }
.result-answered { color: #059669; }
.result-missed { color: #dc2626; font-weight: 600; }
.result-busy { color: #d97706; }

/* IVR */
.ivr-card { padding: 14px; margin-bottom: 10px; }
.ivr-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.ivr-rules { display: flex; flex-direction: column; gap: 4px; margin-bottom: 6px; }
.ivr-rule { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.ivr-digit { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 50%; background: var(--primary); color: white; font-weight: 700; font-size: 12px; flex-shrink: 0; }
.ivr-arrow { color: var(--text-muted); }
.ivr-action { color: var(--text); }
.ivr-meta { font-size: 12px; color: var(--text-muted); }

/* IVR editor */
.ivr-rules-editor { border: 1px solid var(--line); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.ivr-rules-header { display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: 600; }
.ivr-rule-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ivr-rule-label { font-size: 13px; color: var(--text-muted); white-space: nowrap; }

/* Player */
.download-link { display: inline-flex; align-items: center; font-size: 13px; color: var(--primary); text-decoration: none; }
.download-link:hover { text-decoration: underline; }
.text-muted { color: var(--text-muted); }
</style>
