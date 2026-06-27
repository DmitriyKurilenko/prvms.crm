<template>
  <FeatureGate feature="crm_builtin">
    <section class="data-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Импорт и экспорт</h1>
      </div>

      <div class="surface-card toolbar">
        <div class="entity-switch">
          <PButton :label="'Контакты'" size="small" :outlined="entity !== 'contacts'" @click="setEntity('contacts')" />
          <PButton :label="'Компании'" size="small" :outlined="entity !== 'companies'" @click="setEntity('companies')" />
          <PButton :label="'Сделки'" size="small" :outlined="entity !== 'deals'" @click="setEntity('deals')" />
        </div>
        <div class="tab-switch">
          <PButton label="Импорт" icon="pi pi-upload" size="small" text :class="{ active: tab === 'import' }" @click="tab = 'import'" />
          <PButton label="Экспорт" icon="pi pi-download" size="small" text :class="{ active: tab === 'export' }" @click="tab = 'export'" />
          <PButton label="Дубли" icon="pi pi-clone" size="small" text :class="{ active: tab === 'dupes' }" @click="tab = 'dupes'" />
        </div>
      </div>

      <!-- ИМПОРТ -->
      <div v-if="tab === 'import'" class="surface-card pane">
        <p v-if="!canImport" class="muted">У вас нет прав на импорт ({{ entityLabel }}).</p>
        <template v-else>
          <div class="row">
            <input ref="fileInput" type="file" accept=".csv,.xlsx" @change="onFileSelected" />
            <span class="muted">Поддерживаются CSV и XLSX</span>
          </div>

          <div v-if="preview" class="mapping">
            <h3>Сопоставление колонок ({{ preview.total_rows }} строк)</h3>
            <PDataTable :value="preview.headers.map((h) => ({ header: h }))" size="small" stripedRows>
              <PColumn header="Колонка файла">
                <template #body="{ data }">{{ data.header }}</template>
              </PColumn>
              <PColumn header="Поле CRM">
                <template #body="{ data }">
                  <PSelect v-model="mapping[data.header]" :options="fieldOptions" optionLabel="label" optionValue="value" size="small" />
                </template>
              </PColumn>
            </PDataTable>

            <PButton
              label="Импортировать"
              icon="pi pi-play"
              size="small"
              :loading="running"
              :disabled="!hasAnyMapping"
              @click="runImport"
            />
          </div>

          <div v-if="job" class="job-status">
            <PProgressBar :value="jobProgress" />
            <p class="muted">
              Статус: {{ job.status }} · обработано {{ job.processed }}/{{ job.total }} ·
              создано {{ job.created }} · обновлено {{ job.updated }} · ошибок {{ job.errors.length }}
            </p>
            <PDataTable v-if="job.errors.length" :value="job.errors" size="small" :paginator="job.errors.length > 10" :rows="10">
              <PColumn field="row" header="Строка" style="width: 90px" />
              <PColumn field="message" header="Ошибка" />
            </PDataTable>
          </div>
        </template>
      </div>

      <!-- ЭКСПОРТ -->
      <div v-if="tab === 'export'" class="surface-card pane">
        <p v-if="!canExport" class="muted">У вас нет прав на экспорт ({{ entityLabel }}).</p>
        <template v-else>
          <p class="muted">Выгрузка {{ entityLabel.toLowerCase() }} в CSV с учётом ваших прав видимости.</p>
          <PButton label="Скачать CSV" icon="pi pi-download" size="small" :loading="exporting" @click="doExport" />
        </template>
      </div>

      <!-- ДУБЛИ -->
      <div v-if="tab === 'dupes'" class="surface-card pane">
        <p v-if="entity === 'deals'" class="muted">Слияние сделок не поддерживается: сделки — транзакционные записи, дедуп применяется к контактам и компаниям.</p>
        <p v-else-if="!canMerge" class="muted">У вас нет прав на слияние ({{ entityLabel }}).</p>
        <template v-else>
          <PButton label="Найти дубли" icon="pi pi-search" size="small" :loading="dupesLoading" @click="loadDuplicates" />
          <p v-if="dupesLoaded && !groups.length" class="muted">Дублей не найдено.</p>

          <div v-for="(g, gi) in groups" :key="gi" class="dupe-group">
            <div class="dupe-key">Совпадение по «{{ g.key_type }}»: {{ g.key }}</div>
            <div v-for="item in g.items" :key="item.id" class="dupe-item">
              <label><input type="radio" :name="'primary-' + gi" :value="item.id" v-model="primaryByGroup[gi]" /> основной</label>
              <span>{{ item.label }}</span>
            </div>
            <PButton
              label="Объединить"
              icon="pi pi-link"
              size="small"
              :disabled="primaryByGroup[gi] == null"
              @click="doMerge(gi, g)"
            />
          </div>
        </template>
      </div>
    </section>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmDuplicateGroup, CrmImportJob, CrmImportPreview, DataEntity } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('data-tools')
const toast = useToast()
const authStore = useAuthStore()
const perms = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))

const entity = ref<DataEntity>('contacts')
const tab = ref<'import' | 'export' | 'dupes'>('import')

const entityLabel = computed(() => ({ contacts: 'Контакты', companies: 'Компании', deals: 'Сделки' }[entity.value]))
const canImport = computed(() => perms.value[entity.value].can_create)
const canExport = computed(() => perms.value[entity.value].can_view)
const canMerge = computed(() => perms.value[entity.value].can_delete)

/* --- import --- */
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const preview = ref<CrmImportPreview | null>(null)
const mapping = ref<Record<string, string>>({})
const running = ref(false)
const job = ref<CrmImportJob | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const fieldOptions = computed(() => [
  { label: '— не импортировать —', value: '' },
  ...(preview.value?.allowed_fields ?? []).map((f) => ({ label: f, value: f })),
])
const hasAnyMapping = computed(() => Object.values(mapping.value).some((v) => v))
const jobProgress = computed(() => (job.value && job.value.total ? Math.round((job.value.processed / job.value.total) * 100) : 0))

function setEntity(e: DataEntity) {
  entity.value = e
  resetImport()
  groups.value = []
  dupesLoaded.value = false
}

function resetImport() {
  preview.value = null
  mapping.value = {}
  job.value = null
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
  stopPolling()
}

async function onFileSelected(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  selectedFile.value = file
  job.value = null
  try {
    preview.value = await crmApi.importPreview(entity.value, file)
    const m: Record<string, string> = {}
    for (const h of preview.value.headers) m[h] = preview.value.suggested_mapping[h] ?? ''
    mapping.value = m
  } catch (err) {
    log.error('preview failed', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось прочитать файл', life: 5000 })
  }
}

async function runImport() {
  if (!selectedFile.value) return
  const cleaned: Record<string, string> = {}
  for (const [k, v] of Object.entries(mapping.value)) if (v) cleaned[k] = v
  running.value = true
  try {
    const { job_id } = await crmApi.importRun(entity.value, selectedFile.value, cleaned)
    startPolling(job_id)
  } catch (err) {
    log.error('import run failed', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Импорт не запущен', life: 5000 })
  } finally {
    running.value = false
  }
}

function startPolling(jobId: number) {
  stopPolling()
  const tick = async () => {
    try {
      job.value = await crmApi.importJobStatus(jobId)
      if (job.value.status === 'done' || job.value.status === 'failed') {
        stopPolling()
        toast.add({ severity: 'success', summary: 'Импорт завершён', detail: `Создано ${job.value.created}, обновлено ${job.value.updated}`, life: 5000 })
      }
    } catch (err) {
      log.error('poll failed', err)
      stopPolling()
    }
  }
  tick()
  pollTimer = setInterval(tick, 1500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/* --- export --- */
const exporting = ref(false)
async function doExport() {
  exporting.value = true
  try {
    await crmApi.downloadExport(entity.value)
  } catch (err) {
    log.error('export failed', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось выгрузить файл', life: 5000 })
  } finally {
    exporting.value = false
  }
}

/* --- duplicates / merge --- */
const groups = ref<CrmDuplicateGroup[]>([])
const dupesLoading = ref(false)
const dupesLoaded = ref(false)
const primaryByGroup = ref<Record<number, number | null>>({})

async function loadDuplicates() {
  dupesLoading.value = true
  try {
    groups.value = await crmApi.listDuplicates(entity.value)
    primaryByGroup.value = {}
    dupesLoaded.value = true
  } catch (err) {
    log.error('duplicates failed', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось найти дубли', life: 5000 })
  } finally {
    dupesLoading.value = false
  }
}

async function doMerge(groupIndex: number, group: CrmDuplicateGroup) {
  const primaryId = primaryByGroup.value[groupIndex]
  if (primaryId == null) return
  const mergedIds = group.items.map((i) => i.id).filter((id) => id !== primaryId)
  try {
    await crmApi.mergeRecords(entity.value, primaryId, mergedIds)
    toast.add({ severity: 'success', summary: 'Объединено', detail: `Перенесены связи на запись #${primaryId}`, life: 4000 })
    await loadDuplicates()
  } catch (err) {
    log.error('merge failed', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Слияние не выполнено', life: 5000 })
  }
}

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.data-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { padding: 12px 16px; margin-bottom: 12px; display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }
.entity-switch, .tab-switch { display: flex; gap: 6px; }
.tab-switch :deep(.active) { background: var(--p-highlight-bg, rgba(99, 102, 241, 0.12)); }
.pane { padding: 16px; }
.row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.mapping { margin-top: 12px; display: flex; flex-direction: column; gap: 12px; }
.job-status { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
.muted { color: var(--p-text-muted-color); font-size: 13px; }
.dupe-group { border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-top: 12px; }
.dupe-key { font-weight: 600; margin-bottom: 8px; }
.dupe-item { display: flex; gap: 12px; align-items: center; padding: 4px 0; }
.dupe-item label { display: flex; gap: 4px; align-items: center; font-size: 13px; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
