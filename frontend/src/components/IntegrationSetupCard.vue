<template>
  <div class="surface-card setup-card">
    <h3>Подключение внешней CRM</h3>
    <p class="muted">
      Рекомендуемый путь: установка приложения из маркетплейса (OAuth). Быстрый старт: webhook/manual credentials.
    </p>

    <div class="mode-switch">
      <PButton
        label="Рекомендуемый: приложение"
        size="small"
        :outlined="setupMode !== 'marketplace'"
        @click="$emit('update:setupMode', 'marketplace')"
      />
      <PButton
        label="Быстрый старт: webhook"
        size="small"
        :outlined="setupMode !== 'webhook'"
        @click="$emit('update:setupMode', 'webhook')"
      />
    </div>

    <template v-if="setupMode === 'marketplace'">
      <div class="grid">
        <div class="field">
          <label class="field-label">Название подключения</label>
          <PInputText
            :modelValue="marketplaceName"
            @update:modelValue="$emit('update:marketplaceName', $event ?? '')"
            placeholder="Основная интеграция"
          />
        </div>
      </div>
      <div class="actions-row">
        <PButton
          label="Установить amoCRM приложение"
          icon="pi pi-external-link"
          @click="$emit('install', 'amocrm', 'marketplace')"
          :loading="installing === 'amocrm:marketplace'"
          :disabled="!isFeatureEnabled('amocrm')"
        />
        <PButton
          label="Установить Битрикс24 приложение"
          icon="pi pi-external-link"
          severity="secondary"
          @click="$emit('install', 'bitrix24', 'marketplace')"
          :loading="installing === 'bitrix24:marketplace'"
          :disabled="!isFeatureEnabled('bitrix24')"
        />
      </div>
      <div class="actions-row">
        <PButton
          text
          label="OAuth без маркетплейса (amoCRM)"
          @click="$emit('install', 'amocrm', 'oauth')"
          :loading="installing === 'amocrm:oauth'"
          :disabled="!isFeatureEnabled('amocrm')"
        />
        <PButton
          text
          label="OAuth без маркетплейса (Битрикс24)"
          @click="$emit('install', 'bitrix24', 'oauth')"
          :loading="installing === 'bitrix24:oauth'"
          :disabled="!isFeatureEnabled('bitrix24')"
        />
      </div>
    </template>

    <template v-else>
      <form class="webhook-form" @submit.prevent="$emit('submitWebhook')">
        <div class="grid">
          <div class="field">
            <label class="field-label">CRM</label>
            <PSelect
              v-model="form.crm_type"
              :options="crmOptions"
              optionLabel="label"
              optionValue="value"
            />
          </div>
          <div class="field">
            <label class="field-label">Название подключения</label>
            <PInputText v-model="form.name" placeholder="CRM webhook" />
          </div>
        </div>

        <div class="grid" v-if="form.crm_type === 'amocrm'">
          <div class="field">
            <label class="field-label">Base URL</label>
            <PInputText v-model="form.amocrm.base_url" placeholder="https://example.amocrm.ru" />
          </div>
          <div class="field">
            <label class="field-label">Subdomain (опц.)</label>
            <PInputText v-model="form.amocrm.subdomain" placeholder="example" />
          </div>
          <div class="field">
            <label class="field-label">Access Token</label>
            <PInputText v-model="form.amocrm.access_token" placeholder="token" />
          </div>
          <div class="field">
            <label class="field-label">Webhook HMAC Secret (опц.)</label>
            <PInputText v-model="form.amocrm.webhook_hmac_secret" placeholder="hmac secret" />
          </div>
        </div>

        <div class="grid" v-else>
          <div class="field">
            <label class="field-label">Webhook URL</label>
            <PInputText v-model="form.bitrix24.webhook_url" placeholder="https://portal.bitrix24.ru/rest/1/xyz/" />
          </div>
          <div class="field">
            <label class="field-label">Base URL (для OAuth, опц.)</label>
            <PInputText v-model="form.bitrix24.base_url" placeholder="https://portal.bitrix24.ru" />
          </div>
          <div class="field">
            <label class="field-label">Access Token (опц.)</label>
            <PInputText v-model="form.bitrix24.access_token" placeholder="token" />
          </div>
          <div class="field">
            <label class="field-label">User ID (опц.)</label>
            <PInputText v-model="form.bitrix24.user_id" placeholder="1" />
          </div>
          <div class="field">
            <label class="field-label">Application Token (опц.)</label>
            <PInputText v-model="form.bitrix24.application_token" placeholder="app token" />
          </div>
        </div>

        <div class="actions-row">
          <PButton
            type="submit"
            label="Создать webhook-подключение"
            icon="pi pi-plus"
            :loading="creatingWebhook"
            :disabled="!isFeatureEnabled(form.crm_type)"
          />
        </div>
        <p v-if="!isFeatureEnabled(form.crm_type)" class="muted">
          Эта интеграция недоступна на текущем тарифе.
        </p>
      </form>
    </template>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="success">{{ successMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import type { IntegrationType } from '@/types'

/**
 * Presentational shell. `form` is the parent's reactive `quickForm`
 * passed by reference (v-model mutates the same proxy the parent's
 * `createWebhookConnection` reads). `setupMode`/`marketplaceName` are
 * primitives → v-model via props+emit. Actions bubble via emits;
 * `startInstall`/`createWebhookConnection` stay in the parent.
 */
export interface QuickForm {
  crm_type: IntegrationType
  name: string
  amocrm: { base_url: string; subdomain: string; access_token: string; webhook_hmac_secret: string }
  bitrix24: { webhook_url: string; base_url: string; access_token: string; user_id: string; application_token: string }
}

defineProps<{
  setupMode: 'marketplace' | 'webhook'
  marketplaceName: string
  form: QuickForm
  crmOptions: { value: string; label: string }[]
  installing: string
  creatingWebhook: boolean
  errorMessage: string
  successMessage: string
  isFeatureEnabled: (crmType: IntegrationType) => boolean
}>()

defineEmits<{
  'update:setupMode': ['marketplace' | 'webhook']
  'update:marketplaceName': [string]
  install: [IntegrationType, 'oauth' | 'marketplace']
  submitWebhook: []
}>()
</script>

<style scoped>
.setup-card { display: flex; flex-direction: column; gap: 12px; }
.muted { color: var(--text-muted); font-size: 13px; }
.mode-switch { display: flex; gap: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field-label { font-size: 13px; font-weight: 600; }
.webhook-form { display: flex; flex-direction: column; gap: 12px; }
.actions-row { display: flex; gap: 8px; flex-wrap: wrap; }
.error { color: var(--red-500, #dc2626); font-size: 13px; }
.success { color: var(--green-500, #16a34a); font-size: 13px; }
</style>
