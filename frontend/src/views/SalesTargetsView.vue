<template>
  <FeatureGate feature="crm_builtin">
    <section class="targets-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Планы продаж</h1>
      </div>

      <div v-if="!canManage" class="surface-card" style="padding: 14px;">
        Управление планами доступно только владельцу и администратору.
      </div>

      <template v-else>
        <div class="surface-card editor">
          <div class="editor-row">
            <div class="field">
              <label>Месяц</label>
              <input v-model="period" type="month" class="dt-input" @change="reload" />
            </div>
            <div class="field">
              <label>Менеджер</label>
              <PSelect v-model="form.responsible_id" :options="managers" optionLabel="name" optionValue="id" placeholder="Выберите" class="mgr-select" />
            </div>
            <div class="field">
              <label>План по сумме, ₽</label>
              <PInputNumber v-model="form.target_amount" :min="0" mode="decimal" :useGrouping="true" />
            </div>
            <div class="field">
              <label>План по сделкам</label>
              <PInputNumber v-model="form.target_count" :min="0" />
            </div>
            <PButton label="Сохранить план" icon="pi pi-check" size="small" :disabled="!form.responsible_id" @click="save" />
          </div>
        </div>

        <div class="surface-card progress-card">
          <h4>Выполнение за {{ period }}</h4>
          <PDataTable v-responsive-table :value="progress" size="small" stripedRows>
            <PColumn field="manager_name" header="Менеджер" />
            <PColumn header="Сумма (факт / план)">
              <template #body="{ data }">
                <div class="cell-progress">
                  <span>{{ data.actual_amount.toLocaleString() }} / {{ data.target_amount != null ? data.target_amount.toLocaleString() : '—' }} ₽</span>
                  <PProgressBar v-if="data.amount_pct != null" :value="Math.min(100, Math.round(data.amount_pct))" :showValue="true" style="height: 16px" />
                </div>
              </template>
            </PColumn>
            <PColumn header="Сделки (факт / план)">
              <template #body="{ data }">
                <div class="cell-progress">
                  <span>{{ data.actual_count }} / {{ data.target_count != null ? data.target_count : '—' }}</span>
                  <PProgressBar v-if="data.count_pct != null" :value="Math.min(100, Math.round(data.count_pct))" :showValue="true" style="height: 16px" />
                </div>
              </template>
            </PColumn>
            <PColumn header="" style="width: 60px">
              <template #body="{ data }">
                <PButton v-if="targetIdByManager[data.responsible_id]" icon="pi pi-trash" text size="small" severity="danger" @click="removeTarget(data.responsible_id)" />
              </template>
            </PColumn>
            <template #empty>
              <div class="empty-state">Нет планов и закрытых сделок за этот месяц</div>
            </template>
          </PDataTable>
        </div>
      </template>
    </section>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { SalesTarget, TargetProgressRow } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'

const log = createLogger('sales-targets')
const toast = useToast()
const authStore = useAuthStore()
const canManage = computed(() => ['owner', 'admin'].includes(authStore.user?.role ?? ''))

function currentMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const period = ref(currentMonth())
const managers = ref<Array<{ id: number; name: string }>>([])
const progress = ref<TargetProgressRow[]>([])
const targets = ref<SalesTarget[]>([])
const form = reactive<{ responsible_id: number | null; target_amount: number | null; target_count: number | null }>({
  responsible_id: null,
  target_amount: null,
  target_count: null,
})

const targetIdByManager = computed<Record<number, number>>(() => {
  const map: Record<number, number> = {}
  for (const t of targets.value) map[t.responsible_id] = t.id
  return map
})

async function reload() {
  if (!canManage.value) return
  try {
    targets.value = await crmApi.listTargets(period.value)
    progress.value = await crmApi.targetProgress(period.value)
  } catch (err) {
    log.error('Failed to load targets', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить планы', life: 5000 })
  }
}

async function save() {
  if (!form.responsible_id) return
  try {
    await crmApi.upsertTarget({
      period: period.value,
      responsible_id: form.responsible_id,
      target_amount: form.target_amount,
      target_count: form.target_count,
    })
    toast.add({ severity: 'success', summary: 'Сохранено', detail: 'План обновлён', life: 3000 })
    await reload()
  } catch (err) {
    log.error('Failed to save target', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить план', life: 5000 })
  }
}

async function removeTarget(managerId: number) {
  const id = targetIdByManager.value[managerId]
  if (!id) return
  try {
    await crmApi.deleteTarget(id)
    await reload()
  } catch (err) {
    log.error('Failed to delete target', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить план', life: 5000 })
  }
}

onMounted(async () => {
  if (!canManage.value) return
  try {
    managers.value = await crmApi.listManagers()
  } catch (err) {
    log.error('Failed to load managers', err)
  }
  await reload()
})
</script>

<style scoped>
.targets-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.editor { padding: 16px; margin-bottom: 14px; }
.editor-row { display: flex; gap: 14px; align-items: flex-end; flex-wrap: wrap; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; color: var(--p-text-muted-color); }
.mgr-select { min-width: 200px; }
.dt-input { height: 38px; padding: 0 10px; border: 1px solid var(--line, #d1d5db); border-radius: 6px; background: var(--p-inputtext-background, #fff); color: inherit; }
.progress-card { padding: 14px; }
.progress-card h4 { margin: 0 0 10px 0; font-weight: 600; }
.cell-progress { display: flex; flex-direction: column; gap: 4px; min-width: 160px; }
.empty-state { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
