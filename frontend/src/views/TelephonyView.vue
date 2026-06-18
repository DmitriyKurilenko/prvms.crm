<template>
  <FeatureGate feature="telephony">
    <section class="animate-fade">
      <div class="section-header">
        <h1 class="page-title">Телефония</h1>
        <span class="status-pill" :class="'st-' + channel.status">{{ channelStatusLabel }}</span>
      </div>

      <div class="tabs-bar">
        <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <!-- НОМЕР И КАНАЛ -->
      <div v-show="tab === 'channel'" class="tab-pane">
        <div v-if="channel.status === 'active'" class="surface-card pad">
          <p class="muted">Подключённый номер организации</p>
          <p class="big-number">{{ channel.exolve_number }}</p>
          <p class="muted">Входящие звонки этого номера переадресуются ответственному менеджеру; исходящие идут с этого же номера.</p>
        </div>
        <div v-else class="surface-card pad">
          <h3>Подключение номера</h3>
          <p class="muted">Выберите номер — бронь, покупка и настройка переадресации выполнятся автоматически.</p>
          <p v-if="channel.status_detail" class="err">{{ channel.status_detail }}</p>
          <ExolveNumberWizard @connected="onConnected" />
        </div>
      </div>

      <!-- SIP-АККАУНТЫ МЕНЕДЖЕРОВ -->
      <div v-show="tab === 'sip'" class="tab-pane">
        <div class="toolbar">
          <PButton label="Завести SIP всем менеджерам" icon="pi pi-users" :loading="provisioning"
                   :disabled="channel.status !== 'active'" @click="provision" />
          <PButton icon="pi pi-refresh" outlined @click="loadSip" />
        </div>
        <PDataTable :value="sipAccounts" class="mt" v-responsive-table>
          <PColumn field="manager_name" header="Менеджер" />
          <PColumn field="username" header="SIP-логин" />
          <PColumn field="display_number" header="Исходящий номер" />
          <PColumn header="Статус">
            <template #body="{ data }"><span class="status-pill" :class="'st-' + data.status">{{ sipStatusLabel(data.status) }}</span></template>
          </PColumn>
        </PDataTable>
        <p v-if="!sipAccounts.length" class="muted mt">SIP-аккаунты ещё не заведены.</p>
      </div>

      <!-- ЖУРНАЛ ЗВОНКОВ -->
      <div v-show="tab === 'calls'" class="tab-pane">
        <div class="toolbar">
          <PSelect v-model="filters.direction" :options="directionOptions" option-label="label" option-value="value" placeholder="Направление" show-clear class="flt" />
          <PSelect v-model="filters.result" :options="resultOptions" option-label="label" option-value="value" placeholder="Результат" show-clear class="flt" />
          <PButton icon="pi pi-refresh" outlined @click="loadCalls" />
        </div>
        <PDataTable :value="calls" class="mt" v-responsive-table>
          <PColumn header="Тип">
            <template #body="{ data }"><i :class="data.direction === 'inbound' ? 'pi pi-arrow-down-left' : 'pi pi-arrow-up-right'" /></template>
          </PColumn>
          <PColumn field="caller_number" header="От" />
          <PColumn field="called_number" header="Кому" />
          <PColumn header="Результат">
            <template #body="{ data }"><span class="status-pill" :class="'res-' + data.result">{{ resultLabel(data.result) }}</span></template>
          </PColumn>
          <PColumn field="talk_time" header="Разговор, с" />
          <PColumn field="manager_name" header="Менеджер" />
          <PColumn header="Запись">
            <template #body="{ data }">
              <a v-if="data.record_file" :href="data.record_file" target="_blank" rel="noopener"><i class="pi pi-play-circle" /></a>
            </template>
          </PColumn>
          <PColumn header="Время">
            <template #body="{ data }">{{ formatDt(data.started_at) }}</template>
          </PColumn>
        </PDataTable>
        <p v-if="!calls.length" class="muted mt">Звонков пока нет.</p>
      </div>
    </section>
  </FeatureGate>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import ExolveNumberWizard from '@/components/ExolveNumberWizard.vue'
import {
  getChannel, listSipAccounts, provisionSipAccounts, listCalls,
  type ExolveChannelInfo, type SipAccount, type CallRecord, type CallFilters,
} from '@/api/telephony'

const toast = useToast()

type TabKey = 'channel' | 'sip' | 'calls'
const tabs: { key: TabKey; label: string }[] = [
  { key: 'channel', label: 'Номер и канал' },
  { key: 'sip', label: 'SIP-аккаунты' },
  { key: 'calls', label: 'Журнал звонков' },
]
const tab = ref<TabKey>('channel')

const channel = reactive<ExolveChannelInfo>({ exolve_number: '', number_code: '', status: 'draft', status_detail: '', is_active: false })
const sipAccounts = ref<SipAccount[]>([])
const calls = ref<CallRecord[]>([])
const provisioning = ref(false)
const filters = reactive<CallFilters>({})

const directionOptions = [
  { label: 'Входящие', value: 'inbound' },
  { label: 'Исходящие', value: 'outbound' },
]
const resultOptions = [
  { label: 'Отвечен', value: 'answered' },
  { label: 'Пропущен', value: 'missed' },
]

const channelStatusLabel = ref('')
function refreshChannelLabel() {
  const map: Record<string, string> = { draft: 'Не подключён', connecting: 'Подключение…', active: 'Активен', error: 'Ошибка', disabled: 'Отключён' }
  channelStatusLabel.value = map[channel.status] ?? channel.status
}
function sipStatusLabel(s: string) {
  return ({ provisioning: 'Создаётся…', active: 'Активен', error: 'Ошибка', disabled: 'Отключён' } as Record<string, string>)[s] ?? s
}
function resultLabel(s: string) {
  return ({ answered: 'Отвечен', missed: 'Пропущен', busy: 'Занято', failed: 'Ошибка', voicemail: 'Голосовая почта' } as Record<string, string>)[s] ?? s
}
function formatDt(s: string) {
  return s ? new Date(s).toLocaleString('ru-RU') : ''
}

async function loadChannel() {
  try {
    Object.assign(channel, await getChannel())
    refreshChannelLabel()
  } catch { /* feature/permission errors surfaced elsewhere */ }
}
async function loadSip() {
  try { sipAccounts.value = await listSipAccounts() } catch { /* noop */ }
}
async function loadCalls() {
  try { calls.value = await listCalls(filters) } catch { /* noop */ }
}
async function provision() {
  provisioning.value = true
  try {
    const r = await provisionSipAccounts()
    toast.add({ severity: 'success', summary: 'Готово', detail: `Заведено аккаунтов: ${r.provisioned}`, life: 4000 })
    await loadSip()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e instanceof Error ? e.message : '', life: 6000 })
  } finally {
    provisioning.value = false
  }
}
function onConnected() {
  loadChannel()
  loadSip()
  tab.value = 'sip'
}

onMounted(() => {
  loadChannel()
  loadSip()
  loadCalls()
})
</script>

<style scoped>
.pad { padding: 18px; }
.mt { margin-top: 14px; }
.toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.flt { min-width: 170px; }
.muted { color: var(--text-muted, #6b7280); font-size: 14px; }
.err { color: #b91c1c; font-size: 13px; }
.big-number { font-size: 28px; font-weight: 700; margin: 6px 0 12px; }
.status-pill { padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: var(--surface-200, #e5e7eb); }
.status-pill.st-active, .status-pill.res-answered { background: #dcfce7; color: #166534; }
.status-pill.st-error, .status-pill.res-missed { background: #fee2e2; color: #991b1b; }
.status-pill.st-connecting { background: #fef9c3; color: #854d0e; }
</style>
