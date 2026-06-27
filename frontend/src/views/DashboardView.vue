<template>
  <section class="dashboard animate-fade">
    <div class="section-header">
      <h1 class="page-title">Дашборд</h1>
      <div class="quick-actions">
        <RouterLink v-if="hasCrmBuiltin" to="/app/deals">
          <PButton label="Новая сделка" icon="pi pi-plus" size="small" />
        </RouterLink>
        <RouterLink v-if="hasDocuments" to="/app/documents">
          <PButton label="Документ" icon="pi pi-file" size="small" outlined />
        </RouterLink>
      </div>
    </div>

    <!-- KPI Grid -->
    <div class="kpi-grid">
      <article v-for="kpi in kpis" :key="kpi.label" class="surface-card kpi-card" :class="{ locked: kpi.locked }">
        <div class="kpi-icon-wrap" :style="{ background: kpi.iconBg }">
          <i :class="kpi.icon" :style="{ color: kpi.iconColor }" />
        </div>
        <div class="kpi-body">
          <div class="kpi-label">{{ kpi.label }}</div>
          <div class="kpi-value">{{ kpi.value }}</div>
          <div v-if="kpi.secondary" class="kpi-secondary">{{ kpi.secondary }}</div>
          <div v-if="kpi.locked" class="kpi-lock-note">{{ kpi.lockReason }}</div>
        </div>
      </article>
    </div>

    <!-- Bottom grid -->
    <div class="dashboard-grid">
      <!-- Feature links / Quick nav -->
      <div class="surface-card dash-card">
        <div class="dash-card-header">
          <h3 class="section-title">Разделы</h3>
        </div>
        <div class="nav-shortcuts">
          <RouterLink v-for="link in navLinks" :key="link.to" :to="link.to" class="nav-shortcut" :class="{ disabled: !link.allowed }">
            <div class="shortcut-icon" :style="{ background: link.iconBg }">
              <i :class="link.icon" :style="{ color: link.iconColor }" />
            </div>
            <div class="shortcut-label">{{ link.label }}</div>
            <i v-if="!link.allowed" class="pi pi-lock shortcut-lock" />
          </RouterLink>
        </div>
      </div>

      <!-- Plan usage -->
      <div class="surface-card dash-card">
        <div class="dash-card-header">
          <h3 class="section-title">Использование</h3>
          <RouterLink to="/app/subscription" class="dash-link">Подписка →</RouterLink>
        </div>
        <div class="usage-list">
          <div class="usage-row">
            <span class="usage-label">Документы в этом месяце</span>
            <span class="usage-val">{{ tenantStore.plan?.usage?.documents ?? 0 }}</span>
          </div>
          <div class="usage-row">
            <span class="usage-label">Менеджеры</span>
            <span class="usage-val">{{ tenantStore.plan?.usage?.managers ?? 0 }}</span>
          </div>
          <div class="usage-row">
            <span class="usage-label">Пайплайны</span>
            <span class="usage-val">{{ tenantStore.plan?.usage?.pipelines ?? 0 }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/api/http'
import { useTenantStore } from '@/stores/tenant'

const tenantStore = useTenantStore()
const stats = ref<Record<string, number>>({})
const online = ref<{ online: number; total: number } | null>(null)
let pollHandle: ReturnType<typeof setInterval> | null = null

const planReady = computed(() => tenantStore.planLoaded)

const hasAnalytics = computed(() => planReady.value && tenantStore.hasFeature('analytics'))
const hasCrmBuiltin = computed(() => planReady.value && tenantStore.hasFeature('crm_builtin'))
const hasDistribution = computed(() => planReady.value && tenantStore.hasFeature('distribution'))
const hasDocuments = computed(() => planReady.value && tenantStore.hasFeature('documents'))
const hasTelephony = computed(() => planReady.value && tenantStore.hasFeature('telephony'))
const hasChannels = computed(() => planReady.value && tenantStore.hasFeature('messenger_channels'))
const totalManagers = computed(() => tenantStore.plan?.usage?.managers ?? 0)

const kpis = computed(() => [
  {
    label: 'Менеджеры онлайн',
    value: hasAnalytics.value ? (online.value === null ? '…' : String(online.value.online)) : '—',
    secondary: hasAnalytics.value && online.value ? `из ${online.value.total ?? totalManagers.value}` : '',
    icon: 'pi pi-users',
    iconBg: '#eff6ff',
    iconColor: '#3b82f6',
    locked: !hasAnalytics.value,
    lockReason: 'Требуется plan analytics'
  },
  {
    label: 'Открытых сделок',
    value: hasAnalytics.value && hasCrmBuiltin.value ? (stats.value.deals_open ?? 0) : '—',
    secondary: '',
    icon: 'pi pi-chart-bar',
    iconBg: '#f0fdf4',
    iconColor: '#22c55e',
    locked: !hasAnalytics.value || !hasCrmBuiltin.value,
    lockReason: 'Требуется CRM + analytics'
  },
  {
    label: 'Документы (месяц)',
    value: tenantStore.plan?.usage?.documents ?? 0,
    secondary: '',
    icon: 'pi pi-file',
    iconBg: '#fdf4ff',
    iconColor: '#a855f7',
    locked: false,
    lockReason: ''
  },
  {
    label: 'Распределено заявок',
    value: hasAnalytics.value && hasDistribution.value ? (stats.value.distribution_today ?? 0) : '—',
    secondary: 'сегодня',
    icon: 'pi pi-sitemap',
    iconBg: '#fff7ed',
    iconColor: '#f97316',
    locked: !hasAnalytics.value || !hasDistribution.value,
    lockReason: 'Требуется distribution + analytics'
  }
])

const navLinks = computed(() => [
  { to: '/app/contacts', label: 'Контакты', icon: 'pi pi-users', iconBg: '#eff6ff', iconColor: '#3b82f6', allowed: hasCrmBuiltin.value },
  { to: '/app/deals', label: 'Сделки', icon: 'pi pi-chart-bar', iconBg: '#f0fdf4', iconColor: '#22c55e', allowed: hasCrmBuiltin.value },
  { to: '/app/tasks', label: 'Задачи', icon: 'pi pi-check-square', iconBg: '#fdf4ff', iconColor: '#a855f7', allowed: hasCrmBuiltin.value },
  { to: '/app/documents', label: 'Документы', icon: 'pi pi-file', iconBg: '#fff7ed', iconColor: '#f97316', allowed: hasDocuments.value },
  { to: '/app/telephony', label: 'Телефония', icon: 'pi pi-phone', iconBg: '#ecfdf5', iconColor: '#10b981', allowed: hasTelephony.value },
  { to: '/app/channels', label: 'Мессенджеры', icon: 'pi pi-send', iconBg: '#eef2ff', iconColor: '#4f46e5', allowed: hasChannels.value },
  { to: '/app/distribution', label: 'Распределение', icon: 'pi pi-sitemap', iconBg: '#fffbeb', iconColor: '#f59e0b', allowed: hasDistribution.value },
])

async function refreshStats() {
  if (!hasAnalytics.value) return
  try { stats.value = await api<Record<string, number>>('/dashboard/stats/') }
  catch { stats.value = {} }
}

async function refreshOnline() {
  if (!hasAnalytics.value) { online.value = null; return }
  try { online.value = await api<{ online: number; total: number }>('/dashboard/managers-online/') }
  catch { online.value = { online: 0, total: totalManagers.value } }
}

onMounted(async () => {
  await tenantStore.ensureLoaded()
  await Promise.all([refreshStats(), refreshOnline()])
  if (hasAnalytics.value) pollHandle = setInterval(refreshOnline, 30_000)
})

onBeforeUnmount(() => { if (pollHandle) clearInterval(pollHandle) })
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.quick-actions {
  display: flex;
  gap: 8px;
}

/* KPI Cards */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.kpi-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px;
  transition: box-shadow 0.15s;
}

.kpi-card:hover {
  box-shadow: var(--shadow-lg);
}

.kpi-card.locked {
  opacity: 0.75;
}

.kpi-icon-wrap {
  width: 44px;
  height: 44px;
  min-width: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.kpi-body {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}

.kpi-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--text);
  line-height: 1.2;
}

.kpi-secondary {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.kpi-lock-note {
  font-size: 11px;
  color: #f97316;
  margin-top: 4px;
}

/* Dashboard grid */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.dash-card {
  padding: 20px;
}

.dash-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.dash-link {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand);
}

/* Nav shortcuts */
.nav-shortcuts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.nav-shortcut {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  border-radius: 10px;
  text-decoration: none;
  transition: background 0.15s;
  position: relative;
}

.nav-shortcut:hover {
  background: var(--surface-alt);
}

.nav-shortcut.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.shortcut-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.shortcut-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  text-align: center;
}

.shortcut-lock {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 10px;
  color: var(--text-muted);
}

/* Usage list */
.usage-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.usage-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}

.usage-row:last-child {
  border-bottom: none;
}

.usage-label {
  color: var(--text-muted);
  font-weight: 500;
}

.usage-val {
  font-weight: 700;
  color: var(--text);
}

@media (max-width: 1100px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .nav-shortcuts {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 640px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .nav-shortcuts {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
