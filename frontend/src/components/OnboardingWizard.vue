<template>
  <div class="surface-card wizard">
    <h3 class="brand-heading">Настройка организации</h3>
    <p class="step-label">Шаг {{ step }} из 5</p>

    <div class="step-content">
      <!-- Step 1: Organization -->
      <template v-if="step === 1">
        <label class="field-label">Название организации</label>
        <PInputText v-model="form.org_name" placeholder="ООО «Моя компания»" />
        <label class="field-label">Часовой пояс</label>
        <PSelect v-model="form.timezone" :options="timezoneOptions" optionLabel="label" optionValue="value" placeholder="Выберите часовой пояс" />
      </template>

      <!-- Step 2: CRM mode -->
      <template v-else-if="step === 2">
        <label class="field-label">Как вы будете вести клиентскую базу?</label>
        <div class="crm-cards">
          <div
            v-for="opt in crmOptions"
            :key="opt.value"
            class="crm-card surface-card"
            :class="{ selected: form.crm_mode === opt.value }"
            @click="form.crm_mode = opt.value"
          >
            <strong>{{ opt.label }}</strong>
            <small>{{ opt.desc }}</small>
          </div>
        </div>
      </template>

      <!-- Step 3: Managers -->
      <template v-else-if="step === 3">
        <label class="field-label">Добавьте менеджеров вашей команды</label>
        <div v-for="(m, i) in managers" :key="i" class="manager-row">
          <PInputText v-model="m.name" placeholder="Имя" style="flex: 1" />
          <PInputText v-model="m.email" placeholder="Email" style="flex: 1" />
          <PButton icon="pi pi-trash" text severity="danger" @click="removeManager(i)" :disabled="managers.length <= 1" />
        </div>
        <PButton text icon="pi pi-plus" label="Добавить менеджера" @click="addManager" />
      </template>

      <!-- Step 4: Distribution strategy -->
      <template v-else-if="step === 4">
        <label class="field-label">Как распределять входящие заявки между менеджерами?</label>
        <div class="strategy-cards">
          <div
            v-for="s in strategyOptions"
            :key="s.value"
            class="crm-card surface-card"
            :class="{ selected: form.strategy === s.value }"
            @click="form.strategy = s.value"
          >
            <strong>{{ s.label }}</strong>
            <small>{{ s.desc }}</small>
          </div>
        </div>
      </template>

      <!-- Step 5: Done -->
      <template v-else>
        <p>Базовая настройка завершена. Можно переходить в личный кабинет.</p>
      </template>
    </div>

    <div class="actions">
      <PButton text label="Пропустить" @click="confirmSkip" />
      <PButton :label="step < 5 ? 'Сохранить и продолжить' : 'Перейти в ЛК'" :disabled="saving || step > 5" @click="next" />
    </div>

    <PDialog v-model:visible="showSkipDialog" header="Пропустить настройку?" :modal="true" :closable="true" style="width: min(400px, 90vw)">
      <p>Вы уверены? Настройки можно будет изменить позже в разделах ЛК, но визард настройки больше не появится.</p>
      <template #footer>
        <PButton text label="Отмена" @click="showSkipDialog = false" />
        <PButton label="Пропустить" severity="danger" @click="skip" />
      </template>
    </PDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { api } from '@/api/http'
import { useTenantStore } from '@/stores/tenant'

const emit = defineEmits<{ done: [] }>()

const tenantStore = useTenantStore()
const step = ref(Math.max(1, (tenantStore.current?.onboarding_step || 0) + 1))
const saving = ref(false)
const showSkipDialog = ref(false)

const timezoneOptions = [
  { label: 'Калининград (UTC+2)', value: 'Europe/Kaliningrad' },
  { label: 'Москва (UTC+3)', value: 'Europe/Moscow' },
  { label: 'Самара (UTC+4)', value: 'Europe/Samara' },
  { label: 'Екатеринбург (UTC+5)', value: 'Asia/Yekaterinburg' },
  { label: 'Омск (UTC+6)', value: 'Asia/Omsk' },
  { label: 'Красноярск (UTC+7)', value: 'Asia/Krasnoyarsk' },
  { label: 'Иркутск (UTC+8)', value: 'Asia/Irkutsk' },
  { label: 'Якутск (UTC+9)', value: 'Asia/Yakutsk' },
  { label: 'Владивосток (UTC+10)', value: 'Asia/Vladivostok' },
  { label: 'Магадан (UTC+11)', value: 'Asia/Magadan' },
  { label: 'Камчатка (UTC+12)', value: 'Asia/Kamchatka' },
  { label: 'Минск (UTC+3)', value: 'Europe/Minsk' },
  { label: 'Киев (UTC+2)', value: 'Europe/Kiev' },
  { label: 'Алма-Ата (UTC+6)', value: 'Asia/Almaty' },
  { label: 'Ташкент (UTC+5)', value: 'Asia/Tashkent' },
]

const crmOptions = [
  { value: 'builtin', label: 'Встроенный CRM', desc: 'Воронки, сделки, контакты — всё внутри платформы' },
  { value: 'amocrm', label: 'amoCRM', desc: 'Интеграция с amoCRM — данные синхронизируются автоматически' },
  { value: 'bitrix24', label: 'Битрикс24', desc: 'Интеграция с Битрикс24 через webhook или OAuth' },
]

const strategyOptions = [
  { value: 'round_robin', label: 'По очереди', desc: 'Заявки назначаются менеджерам строго по очереди' },
  { value: 'min_load', label: 'Равномерно', desc: 'Заявка уходит менеджеру с наименьшей нагрузкой' },
  { value: 'weighted', label: 'По весам', desc: 'Менеджеры с бо́льшим весом получают больше заявок' },
  { value: 'manual_queue', label: 'Ручная очередь', desc: 'Заявки попадают в общую очередь, менеджеры берут сами' },
]

const form = reactive({
  org_name: tenantStore.current?.name || '',
  timezone: tenantStore.current?.timezone || 'Europe/Moscow',
  crm_mode: tenantStore.current?.crm_mode || 'builtin',
  strategy: 'round_robin',
})

const managers = reactive<Array<{ name: string; email: string }>>([
  { name: '', email: '' },
])

const addManager = () => {
  managers.push({ name: '', email: '' })
}

const removeManager = (i: number) => {
  if (managers.length > 1) managers.splice(i, 1)
}

const buildPayload = () => {
  if (step.value === 3) {
    const valid = managers.filter(m => m.email.trim())
    return { ...form, managers: valid }
  }
  return { ...form }
}

const next = async () => {
  if (step.value > 5) return
  saving.value = true
  try {
    const data = await api<{ onboarding_step: number }>(`/onboarding/step/${step.value}/`, {
      method: 'POST',
      body: buildPayload(),
    })
    step.value = Math.min(5, data.onboarding_step + 1)
    await tenantStore.reloadTenant()
    if (step.value > 5 || tenantStore.current?.onboarding_step === 5) {
      emit('done')
    }
  } finally {
    saving.value = false
  }
}

const confirmSkip = () => {
  showSkipDialog.value = true
}

const skip = async () => {
  showSkipDialog.value = false
  await api('/onboarding/skip/', { method: 'POST' })
  await tenantStore.reloadTenant()
  emit('done')
}
</script>

<style scoped>
.wizard {
  padding: 16px;
}

.step-label {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.field-label {
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 2px;
}

.step-content {
  display: grid;
  gap: 10px;
  margin: 14px 0;
}

.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.crm-cards,
.strategy-cards {
  display: grid;
  gap: 8px;
}

.crm-card {
  padding: 12px;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.crm-card:hover {
  border-color: var(--primary-300, #a5b4fc);
}

.crm-card.selected {
  border-color: var(--primary-500, #6366f1);
  background: var(--primary-50, rgba(99, 102, 241, 0.06));
}

.crm-card strong {
  display: block;
  margin-bottom: 2px;
}

.crm-card small {
  color: var(--text-muted);
}

.manager-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
