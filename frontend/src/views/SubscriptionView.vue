<template>
  <section class="subscription-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Подписка</h1>
    </div>

    <!-- Trial / Subscription status -->
    <div class="surface-card status-card" v-if="tenant">
      <div class="status-header">
        <div>
          <h3>{{ plan?.plan_name ?? '—' }}</h3>
          <span class="status-badge" :class="statusClass">{{ statusLabel }}</span>
        </div>
        <div v-if="tenant.trial_active && tenant.trial_expires_at" class="trial-countdown">
          <i class="pi pi-clock" /> Осталось {{ daysLeft }} дн.
        </div>
      </div>

      <div class="usage-grid" v-if="plan">
        <div v-for="row in usageRows" :key="row.label" class="usage-item">
          <div class="usage-label">
            <span>{{ row.label }}</span>
            <strong>{{ row.value }}</strong>
          </div>
          <PProgressBar :value="row.percent" />
        </div>
      </div>
    </div>

    <!-- Plan change (only during trial) -->
    <div class="surface-card plans-card" v-if="tenant?.trial_active || tenant?.trial_expired">
      <h3>{{ tenant?.is_paid ? 'Сменить тариф' : 'Выбрать тариф и оплатить' }}</h3>

      <div class="plans-grid">
        <div
          v-for="p in plans"
          :key="p.slug"
          class="plan-tile"
          :class="{ current: p.slug === plan?.plan_slug }"
        >
          <strong>{{ p.name }}</strong>
          <div class="plan-price">{{ p.price_monthly > 0 ? `${p.price_monthly} ₽/мес` : 'Бесплатно' }}</div>
          <ul class="plan-limits">
            <li>Менеджеров: {{ p.max_managers ?? '∞' }}</li>
            <li>Договоров/мес: {{ p.max_contracts_per_month ?? '∞' }}</li>
            <li>CRM-подключений: {{ p.max_crm_connections ?? '∞' }}</li>
            <li>Воронок: {{ p.max_pipelines ?? '∞' }}</li>
          </ul>

          <div class="plan-actions">
            <PButton
              v-if="tenant?.trial_active && p.slug !== plan?.plan_slug"
              label="Переключить"
              severity="secondary"
              size="small"
              @click="doChangePlan(p.slug)"
              :loading="changingPlan === p.slug"
            />
            <PButton
              v-if="!tenant?.is_paid && p.price_monthly > 0"
              label="Оплатить"
              size="small"
              @click="doCheckout(p.slug)"
              :loading="checkingOut === p.slug"
            />
            <span v-if="p.slug === plan?.plan_slug" class="current-label">Текущий</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Checkout form -->
    <div class="surface-card checkout-card" v-if="showCheckout">
      <h3>Оформление подписки: {{ checkoutPlanName }}</h3>
      <div class="checkout-form">
        <label class="text-sm font-semibold">Период оплаты (мес.)</label>
        <PSelect v-model="checkoutMonths" :options="monthOptions" optionLabel="label" optionValue="value" />
        <div class="checkout-total">
          Итого: <strong>{{ checkoutTotal }} ₽</strong>
        </div>
        <PButton label="Перейти к оплате" @click="confirmCheckout" :loading="submittingCheckout" />
        <PButton label="Отмена" severity="secondary" text @click="showCheckout = false" />
      </div>
      <p v-if="checkoutResult" class="checkout-message">{{ checkoutResult }}</p>
    </div>

    <!-- Payment history -->
    <div class="surface-card payments-card">
      <h3>История платежей</h3>
      <PDataTable v-responsive-table :value="payments" size="small" :paginator="payments.length > 5" :rows="5" emptyMessage="Платежей пока нет">
        <PColumn field="plan_name" header="Тариф" />
        <PColumn field="amount" header="Сумма">
          <template #body="{ data }">{{ data.amount }} ₽</template>
        </PColumn>
        <PColumn field="months" header="Мес." />
        <PColumn field="status" header="Статус">
          <template #body="{ data }">
            <span :class="'payment-status-' + data.status">{{ paymentStatusLabel(data.status) }}</span>
          </template>
        </PColumn>
        <PColumn field="created_at" header="Дата">
          <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
        </PColumn>
      </PDataTable>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTenantStore } from '@/stores/tenant'
import { checkout, changePlan, getPayments } from '@/api/tenant'
import { formatDate as fmtDate } from '@/utils/datetime'
import type { CheckoutResponse } from '@/api/tenant'

const tenantStore = useTenantStore()
const { current: tenant, plan, availablePlans: plans } = storeToRefs(tenantStore)

const payments = ref<Array<Record<string, unknown>>>([])
const changingPlan = ref<string | null>(null)
const checkingOut = ref<string | null>(null)

// Checkout state
const showCheckout = ref(false)
const checkoutSlug = ref('')
const checkoutMonths = ref(1)
const submittingCheckout = ref(false)
const checkoutResult = ref('')

const monthOptions = [
  { label: '1 месяц', value: 1 },
  { label: '3 месяца', value: 3 },
  { label: '6 месяцев', value: 6 },
  { label: '12 месяцев', value: 12 },
]

const checkoutPlanName = computed(() => {
  const p = plans.value.find((item) => item.slug === checkoutSlug.value)
  return p?.name || checkoutSlug.value
})

const checkoutPlanPrice = computed(() => {
  const p = plans.value.find((item) => item.slug === checkoutSlug.value)
  return p?.price_monthly || 0
})

const checkoutTotal = computed(() => checkoutPlanPrice.value * checkoutMonths.value)

const daysLeft = computed(() => {
  if (!tenant.value?.trial_expires_at) return 0
  const diff = new Date(tenant.value.trial_expires_at).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
})

const statusClass = computed(() => {
  if (tenant.value?.is_paid) return 'status-paid'
  if (tenant.value?.trial_expired) return 'status-expired'
  return 'status-trial'
})

const statusLabel = computed(() => {
  if (tenant.value?.is_paid) return 'Оплачен'
  if (tenant.value?.trial_expired) return 'Пробный период истёк'
  return 'Пробный период'
})

const pct = (current: number, limit: number | null) => {
  if (limit === null || limit === 0) return 0
  return Math.min(100, Math.round((current / limit) * 100))
}

const usageRows = computed(() => {
  if (!plan.value) return []
  return [
    {
      label: 'Менеджеры',
      value: `${plan.value.usage.managers}/${plan.value.max_managers ?? '∞'}`,
      percent: pct(plan.value.usage.managers, plan.value.max_managers)
    },
    {
      label: 'Договоры в месяц',
      value: `${plan.value.usage.contracts}/${plan.value.max_contracts_per_month ?? '∞'}`,
      percent: pct(plan.value.usage.contracts, plan.value.max_contracts_per_month)
    },
    {
      label: 'CRM-подключения',
      value: `${plan.value.usage.crm_connections}/${plan.value.max_crm_connections ?? '∞'}`,
      percent: pct(plan.value.usage.crm_connections, plan.value.max_crm_connections)
    },
    {
      label: 'Воронки',
      value: `${plan.value.usage.pipelines}/${plan.value.max_pipelines ?? '∞'}`,
      percent: pct(plan.value.usage.pipelines, plan.value.max_pipelines)
    }
  ]
})

function paymentStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: 'Ожидает оплаты',
    paid: 'Оплачен',
    cancelled: 'Отменён',
    refunded: 'Возврат',
  }
  return map[status] || status
}

const formatDate = (iso: string) => fmtDate(iso)

async function doChangePlan(slug: string) {
  changingPlan.value = slug
  try {
    await changePlan(slug)
    await tenantStore.reloadPlan()
    await tenantStore.reloadTenant()
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: string } })?.data?.detail
    alert(detail || 'Не удалось сменить план')
  } finally {
    changingPlan.value = null
  }
}

function doCheckout(slug: string) {
  checkoutSlug.value = slug
  checkoutMonths.value = 1
  checkoutResult.value = ''
  showCheckout.value = true
}

async function confirmCheckout() {
  submittingCheckout.value = true
  try {
    const res: CheckoutResponse = await checkout(checkoutSlug.value, checkoutMonths.value)
    if (res.confirmation_url) {
      window.location.href = res.confirmation_url
      return
    }
    checkoutResult.value = 'Ошибка: не получена ссылка на оплату'
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: string } })?.data?.detail
    checkoutResult.value = detail || 'Ошибка при создании платежа'
  } finally {
    submittingCheckout.value = false
  }
}

async function loadPayments() {
  try {
    payments.value = await getPayments()
  } catch {
    // ignore
  }
}

onMounted(async () => {
  await tenantStore.ensureLoaded()
  await tenantStore.loadAvailablePlans()
  await loadPayments()

  // After return from YooKassa payment page, refresh tenant state
  await tenantStore.reloadTenant()
})
</script>

<style scoped>
.subscription-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.status-card,
.plans-card,
.checkout-card,
.payments-card {
  padding: 16px;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  margin-top: 4px;
}

.status-trial {
  background: var(--p-yellow-100);
  color: var(--p-yellow-800);
}

.status-expired {
  background: var(--p-red-100);
  color: var(--p-red-800);
}

.status-paid {
  background: var(--p-green-100);
  color: var(--p-green-800);
}

.trial-countdown {
  font-size: 14px;
  color: var(--p-yellow-700);
  display: flex;
  align-items: center;
  gap: 6px;
}

.usage-grid {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.usage-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2px;
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.plan-tile {
  border: 2px solid var(--p-surface-200);
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plan-tile.current {
  border-color: var(--p-primary-400);
}

.plan-price {
  font-size: 15px;
  color: var(--p-primary-600);
  font-weight: 700;
}

.plan-limits {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.plan-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.current-label {
  font-size: 12px;
  color: var(--p-primary-500);
  font-weight: 600;
}

.checkout-form {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  max-width: 320px;
}

.checkout-total {
  font-size: 18px;
  margin: 4px 0;
}

.checkout-message {
  margin-top: 10px;
  color: var(--p-green-700);
  font-weight: 500;
}

.payment-status-pending { color: var(--p-yellow-700); }
.payment-status-paid { color: var(--p-green-700); font-weight: 600; }
.payment-status-cancelled { color: var(--text-muted); }
.payment-status-refunded { color: var(--p-red-600); }
</style>
