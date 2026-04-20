<template>
  <section class="settings-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Настройки организации</h1>
    </div>

    <div class="surface-card" style="padding: 16px; max-width: 720px">
      <form @submit.prevent="save" class="settings-form">
        <label class="field">
          <span class="label-text">Название</span>
          <PInputText v-model="form.name" placeholder="Название организации" />
        </label>

        <label class="field">
          <span class="label-text">Цвет бренда</span>
          <div class="color-row">
            <input type="color" v-model="form.brand_color" class="color-picker" />
            <PInputText v-model="form.brand_color" placeholder="#10b981" />
          </div>
        </label>

        <label class="field">
          <span class="label-text">Таймзона</span>
          <PSelect
            v-model="form.timezone"
            :options="timezoneOptions"
            filter
            :loading="!timezoneOptions.length"
            placeholder="Europe/Moscow"
            style="width: 100%"
          />
        </label>

        <label class="field">
          <span class="label-text">Язык</span>
          <PSelect
            v-model="form.language"
            :options="languageOptions"
            option-value="code"
            option-label="label"
            style="width: 100%"
          />
        </label>

        <div class="field">
          <span class="label-text">Логотип</span>
          <div class="logo-row">
            <div class="logo-preview">
              <img v-if="logoUrl" :src="logoUrl" alt="Логотип организации" />
              <div v-else class="logo-placeholder">Нет логотипа</div>
            </div>
            <div class="logo-actions">
              <input
                ref="fileInputRef"
                type="file"
                accept="image/png,image/jpeg,image/svg+xml,image/webp"
                class="hidden-file-input"
                @change="onFilePicked"
              />
              <PButton
                type="button"
                label="Загрузить"
                icon="pi pi-upload"
                :loading="uploading"
                @click="fileInputRef?.click()"
              />
              <PButton
                v-if="logoUrl"
                type="button"
                label="Удалить"
                icon="pi pi-trash"
                severity="secondary"
                outlined
                :loading="deleting"
                @click="removeLogo"
              />
            </div>
          </div>
          <small class="hint">PNG, JPEG, SVG или WEBP, до 2 МБ.</small>
        </div>

        <div v-if="errorMessage" class="error">{{ errorMessage }}</div>

        <div class="actions">
          <PButton type="submit" label="Сохранить" icon="pi pi-save" :loading="saving" />
          <span v-if="savedFlash" class="saved-flash">Настройки сохранены</span>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useTenantStore } from '@/stores/tenant'

const tenantStore = useTenantStore()

const form = reactive({
  name: '',
  brand_color: '#10b981',
  timezone: 'Europe/Moscow',
  language: 'ru'
})

const fileInputRef = ref<HTMLInputElement | null>(null)
const saving = ref(false)
const uploading = ref(false)
const deleting = ref(false)
const savedFlash = ref(false)
const errorMessage = ref('')

const logoUrl = computed(() => tenantStore.current?.logo_url || '')

const languageOptions = [
  { code: 'ru', label: 'Русский' },
  { code: 'en', label: 'English' }
]

const timezoneOptions = ref<string[]>([])

function loadTimezoneOptions() {
  try {
    const supported = (Intl as unknown as { supportedValuesOf?: (kind: string) => string[] }).supportedValuesOf
    if (typeof supported === 'function') {
      timezoneOptions.value = supported('timeZone') as string[]
      return
    }
  } catch {
    // ignore
  }
  timezoneOptions.value = [
    'UTC',
    'Europe/Moscow',
    'Europe/Kaliningrad',
    'Europe/Samara',
    'Asia/Yekaterinburg',
    'Asia/Omsk',
    'Asia/Novosibirsk',
    'Asia/Krasnoyarsk',
    'Asia/Irkutsk',
    'Asia/Vladivostok',
    'Asia/Magadan',
    'Asia/Kamchatka',
    'Europe/London',
    'Europe/Berlin',
    'Europe/Paris',
    'America/New_York',
    'America/Los_Angeles'
  ]
}

onMounted(async () => {
  loadTimezoneOptions()
  await tenantStore.ensureLoaded()
  const current = tenantStore.current
  if (current) {
    form.name = current.name || ''
    form.brand_color = current.brand_color || '#10b981'
    form.timezone = current.timezone || 'Europe/Moscow'
    form.language = current.language || 'ru'
  }
})

async function save() {
  saving.value = true
  errorMessage.value = ''
  try {
    await tenantStore.saveSettings({ ...form })
    savedFlash.value = true
    setTimeout(() => (savedFlash.value = false), 1800)
  } catch (err) {
    errorMessage.value = extractMessage(err, 'Не удалось сохранить настройки')
  } finally {
    saving.value = false
  }
}

async function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files && input.files[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  errorMessage.value = ''
  try {
    await tenantStore.uploadLogo(file)
  } catch (err) {
    errorMessage.value = extractMessage(err, 'Не удалось загрузить логотип')
  } finally {
    uploading.value = false
  }
}

async function removeLogo() {
  deleting.value = true
  errorMessage.value = ''
  try {
    await tenantStore.removeLogo()
  } catch (err) {
    errorMessage.value = extractMessage(err, 'Не удалось удалить логотип')
  } finally {
    deleting.value = false
  }
}

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { data?: { detail?: string }; message?: string }
  return e?.data?.detail || e?.message || fallback
}
</script>

<style scoped>
.settings-form {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
}

.label-text {
  font-weight: 600;
  color: var(--text);
  font-size: 13px;
}

.color-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.color-picker {
  width: 52px;
  height: 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 2px;
  background: transparent;
  cursor: pointer;
}

.logo-row {
  display: flex;
  gap: 16px;
  align-items: center;
}

.logo-preview {
  width: 96px;
  height: 96px;
  border: 1px solid var(--line);
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: var(--surface);
  overflow: hidden;
}

.logo-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.logo-placeholder {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  padding: 8px;
}

.logo-actions {
  display: flex;
  gap: 8px;
}

.hidden-file-input {
  display: none;
}

.hint {
  color: var(--text-muted);
  font-size: 12px;
}

.error {
  color: var(--danger);
  font-size: 13px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.saved-flash {
  color: #16a34a;
  font-size: 13px;
}
</style>
