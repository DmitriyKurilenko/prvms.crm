<template>
  <div class="register-page">
    <div class="surface-card register-card fade-in-up">
      <h1 class="brand-heading">Регистрация организации</h1>
      <p>Создайте компанию и аккаунт владельца. Пробный период — 7 дней на любом тарифе.</p>

      <form class="form" @submit.prevent="submit">
        <PInputText v-model="orgName" placeholder="Название организации" @update:model-value="syncSlug" />
        <PInputText v-model="orgSlug" placeholder="Слаг организации (например, acme)" />
        <PInputText v-model="username" placeholder="Имя пользователя owner" />
        <PInputText v-model="email" placeholder="Email owner" />
        <PPassword v-model="password" placeholder="Пароль" :feedback="false" toggle-mask />
        <PPassword v-model="confirmPassword" placeholder="Повторите пароль" :feedback="false" toggle-mask />

        <div class="plan-selector">
          <label class="text-sm font-semibold">Тарифный план (триал 7 дней)</label>
          <div class="plan-cards">
            <div
              v-for="p in plans"
              :key="p.slug"
              class="plan-card"
              :class="{ selected: selectedPlan === p.slug }"
              @click="selectedPlan = p.slug"
            >
              <strong>{{ p.name }}</strong>
              <span class="plan-price">{{ p.price_monthly > 0 ? `${p.price_monthly} ₽/мес` : 'Бесплатно' }}</span>
              <ul class="plan-features">
                <li>Менеджеров: {{ p.max_managers ?? '∞' }}</li>
                <li>Договоров/мес: {{ p.max_contracts_per_month ?? '∞' }}</li>
                <li>CRM-подключений: {{ p.max_crm_connections ?? '∞' }}</li>
                <li>Воронок: {{ p.max_pipelines ?? '∞' }}</li>
              </ul>
            </div>
          </div>
        </div>

        <PButton :loading="auth.loading" type="submit" label="Зарегистрировать организацию" />
      </form>

      <small v-if="error" class="error">{{ error }}</small>
      <small class="hint">
        Уже есть доступ?
        <RouterLink to="/login">Войти</RouterLink>
      </small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/http'
import type { PlanCatalogItem } from '@/types'

const router = useRouter()
const auth = useAuthStore()

const orgName = ref('')
const orgSlug = ref('')
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const plans = ref<PlanCatalogItem[]>([])
const selectedPlan = ref('simple')

onMounted(async () => {
  try {
    plans.value = await api<PlanCatalogItem[]>('/billing/plans/')
    if (plans.value.length && !plans.value.find(p => p.slug === selectedPlan.value)) {
      selectedPlan.value = plans.value[0].slug
    }
  } catch {
    // fallback — allow registration even if plans fail to load
  }
})

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

function syncSlug(value: string): void {
  if (!orgSlug.value) {
    orgSlug.value = slugify(value)
  }
}

const submit = async () => {
  error.value = ''

  if (!orgName.value || !orgSlug.value || !username.value || !email.value || !password.value) {
    error.value = 'Заполните все обязательные поля.'
    return
  }

  if (password.value !== confirmPassword.value) {
    error.value = 'Пароли не совпадают.'
    return
  }

  if (!selectedPlan.value) {
    error.value = 'Выберите тарифный план.'
    return
  }

  try {
    await auth.register({
      org_name: orgName.value.trim(),
      org_slug: slugify(orgSlug.value),
      username: username.value.trim(),
      email: email.value.trim().toLowerCase(),
      password: password.value,
      plan_slug: selectedPlan.value
    })
    await router.push('/app')
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: string } })?.data?.detail
    error.value = detail || 'Не удалось завершить регистрацию. Проверьте данные и попробуйте снова.'
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
}

.register-card {
  width: min(640px, 100%);
  padding: 24px;
}

p {
  color: var(--text-muted);
}

.form {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.plan-selector {
  margin-top: 8px;
}

.plan-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  margin-top: 8px;
}

.plan-card {
  border: 2px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.plan-card:hover {
  border-color: var(--brand);
}

.plan-card.selected {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.plan-price {
  font-size: 13px;
  color: var(--brand);
  font-weight: 600;
}

.plan-features {
  list-style: none;
  padding: 0;
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.plan-features li::before {
  content: '✓ ';
}

.error {
  color: var(--danger);
  margin-top: 10px;
  display: block;
}

.hint {
  display: block;
  margin-top: 8px;
  color: var(--text-muted);
}
</style>
