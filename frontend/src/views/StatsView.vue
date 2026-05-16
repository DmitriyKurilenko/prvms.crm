<template>
  <FeatureGate feature="crm_builtin">
    <section class="stats-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Аналитика CRM</h1>
      </div>

      <div v-if="!canUseStats" class="surface-card" style="padding: 14px;">
        У вас нет прав для просмотра аналитики.
      </div>

      <template v-else>
        <div class="toolbar">
          <PSelect
            v-model="pipelineId"
            :options="pipelines"
            optionLabel="name"
            optionValue="id"
            placeholder="Воронка"
            class="toolbar-select"
            @change="load"
          />
        </div>

        <div v-if="pipelineStatsData.length" class="stats-section surface-card">
          <h4>Конверсия по воронке</h4>
          <PDataTable v-responsive-table :value="pipelineStatsData" size="small" stripedRows>
            <PColumn field="stage_name" header="Этап" />
            <PColumn field="total" header="Сделок" />
            <PColumn field="amount" header="Сумма">
              <template #body="{ data }">
                {{ data.amount ? data.amount.toLocaleString() + ' ₽' : '—' }}
              </template>
            </PColumn>
            <PColumn header="Доля">
              <template #body="{ data }">
                <PProgressBar :value="pipelineTotal ? Math.round(data.total / pipelineTotal * 100) : 0" :showValue="true" style="height: 20px" />
              </template>
            </PColumn>
          </PDataTable>
        </div>

        <div v-if="managerStatsData.length" class="stats-section surface-card">
          <h4>Сделки по менеджерам</h4>
          <PDataTable v-responsive-table :value="managerStatsData" size="small" stripedRows>
            <PColumn header="Менеджер">
              <template #body="{ data }">
                {{ data.manager_name || 'Не назначен' }}
              </template>
            </PColumn>
            <PColumn field="total" header="Сделок" />
            <PColumn field="amount" header="Сумма">
              <template #body="{ data }">
                {{ data.amount ? data.amount.toLocaleString() + ' ₽' : '—' }}
              </template>
            </PColumn>
          </PDataTable>
        </div>

        <div v-if="!pipelineStatsData.length && !managerStatsData.length" class="empty-state">
          Выберите воронку для просмотра статистики
        </div>
      </template>
    </section>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmPipeline } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('stats')
const toast = useToast()
const authStore = useAuthStore()
const crmPermissions = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canUseStats = computed(() => crmPermissions.value.deals.can_view)

const pipelines = ref<CrmPipeline[]>([])
const pipelineId = ref<number | null>(null)
const pipelineStatsData = ref<Array<{ stage_name: string; total: number; amount: number }>>([])
const managerStatsData = ref<Array<{ manager_name: string | null; total: number; amount: number }>>([])
const pipelineTotal = computed(() => pipelineStatsData.value.reduce((sum, s) => sum + s.total, 0))

async function loadPipelines() {
  if (!canUseStats.value) return
  try {
    pipelines.value = await crmApi.listPipelines()
    if (pipelines.value.length && !pipelineId.value) {
      pipelineId.value = pipelines.value[0].id
    }
  } catch (err) {
    log.error('Failed to load pipelines', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить воронки', life: 5000 })
  }
}

async function load() {
  if (!canUseStats.value) {
    pipelineStatsData.value = []
    managerStatsData.value = []
    return
  }
  try {
    if (pipelineId.value) {
      pipelineStatsData.value = await crmApi.pipelineStats(pipelineId.value)
    }
    managerStatsData.value = await crmApi.managerStats()
  } catch (err) {
    log.error('Failed to load stats', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить статистику', life: 5000 })
  }
}

onMounted(async () => {
  await loadPipelines()
  await load()
})
</script>

<style scoped>
.stats-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.toolbar-select { min-width: 220px; }
.stats-section { padding: 14px; margin-bottom: 14px; }
.stats-section h4 { margin: 0 0 10px 0; font-weight: 600; }
.empty-state { padding: 30px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
