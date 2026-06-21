<template>
  <div>
    <div class="surface-card" style="padding: 16px; margin-bottom: 12px">
      <h3 style="margin: 0 0 12px">{{ editingId ? 'Редактировать канал' : 'Подключить канал' }}</h3>
      <form @submit.prevent="$emit('submit')" style="display: flex; flex-direction: column; gap: 10px">
        <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end">
          <div style="min-width: 200px">
            <label class="field-label">Название</label>
            <PInputText v-model="form.name" placeholder="Мой Telegram бот" style="width: 100%" />
          </div>
          <div style="min-width: 180px">
            <label class="field-label">Тип</label>
            <PSelect v-model="form.channel_type" :options="typeOptions" optionLabel="label" optionValue="value"
              placeholder="Выберите тип" style="width: 100%" :disabled="!!editingId" />
          </div>
        </div>

        <!-- Dynamic credentials -->
        <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end">
          <template v-if="form.channel_type === 'telegram'">
            <div style="min-width: 300px; flex: 1">
              <label class="field-label">Bot Token</label>
              <PInputText v-model="form.credentials.bot_token" placeholder="123456:ABC-DEF..." style="width: 100%" />
            </div>
          </template>
          <template v-if="form.channel_type === 'whatsapp' || form.channel_type === 'whatsapp_business'">
            <div style="min-width: 250px; flex: 1">
              <label class="field-label">Send URL</label>
              <PInputText v-model="form.credentials.send_url" placeholder="https://api.provider.com/send" style="width: 100%" />
            </div>
            <div style="min-width: 200px">
              <label class="field-label">Auth Token</label>
              <PInputText v-model="form.credentials.auth_token" placeholder="Bearer token" style="width: 100%" />
            </div>
          </template>
          <template v-if="form.channel_type === 'max'">
            <div style="min-width: 300px; flex: 1">
              <label class="field-label">Bot Token</label>
              <PInputText v-model="form.credentials.bot_token" placeholder="AAHdqTcvCH1vGWJx..." style="width: 100%" />
            </div>
          </template>
          <template v-if="form.channel_type === 'email'">
            <div style="min-width: 220px; flex: 1">
              <label class="field-label">IMAP-хост</label>
              <PInputText v-model="form.credentials.imap_host" placeholder="imap.example.com" style="width: 100%" />
            </div>
            <div style="min-width: 100px">
              <label class="field-label">IMAP-порт</label>
              <PInputText v-model.number="form.credentials.imap_port" type="number" style="width: 100%" />
            </div>
            <div style="min-width: 220px; flex: 1">
              <label class="field-label">SMTP-хост</label>
              <PInputText v-model="form.credentials.smtp_host" placeholder="smtp.example.com" style="width: 100%" />
            </div>
            <div style="min-width: 100px">
              <label class="field-label">SMTP-порт</label>
              <PInputText v-model.number="form.credentials.smtp_port" type="number" style="width: 100%" />
            </div>
            <div style="min-width: 220px; flex: 1">
              <label class="field-label">Логин (email)</label>
              <PInputText v-model="form.credentials.username" placeholder="sales@example.com" style="width: 100%" />
            </div>
            <div style="min-width: 180px">
              <label class="field-label">Пароль</label>
              <PInputText v-model="form.credentials.password" type="password" placeholder="••••••" style="width: 100%" />
            </div>
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer">
              <input type="checkbox" v-model="form.credentials.imap_ssl" />
              <span class="field-label" style="margin: 0">IMAP SSL</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer">
              <input type="checkbox" v-model="form.credentials.smtp_ssl" />
              <span class="field-label" style="margin: 0">SMTP SSL</span>
            </label>
          </template>
          <div v-if="form.channel_type !== 'email'" style="min-width: 200px">
            <label class="field-label">Webhook Token (опц.)</label>
            <PInputText v-model="form.credentials.webhook_token" placeholder="Секрет для верификации" style="width: 100%" />
          </div>
        </div>

        <div style="display: flex; gap: 16px; flex-wrap: wrap; align-items: center">
          <label style="display: flex; align-items: center; gap: 6px; cursor: pointer">
            <input type="checkbox" v-model="form.auto_create_lead" />
            <span class="field-label" style="margin: 0">Создавать сделку при первом сообщении</span>
          </label>
        </div>

        <div>
          <label class="field-label">Приветственное сообщение (опц.)</label>
          <PTextarea v-model="form.welcome_message" rows="2" placeholder="Отправляется клиенту при первом обращении" style="width: 100%; max-width: 500px" />
        </div>

        <div style="display: flex; gap: 8px; align-items: center">
          <PButton type="submit" :label="editingId ? 'Сохранить' : 'Подключить'" :icon="editingId ? 'pi pi-check' : 'pi pi-plus'" />
          <PButton v-if="editingId" label="Отмена" text @click="$emit('cancel')" />
        </div>
      </form>
    </div>

    <div class="surface-card" style="padding: 16px">
      <PDataTable v-responsive-table :value="channels" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
        <PColumn field="name" header="Название" />
        <PColumn header="Тип">
          <template #body="{ data }">
            <div style="display: flex; align-items: center; gap: 6px">
              <img v-if="data.channel_type === 'vk'" src="@/assets/icons/vk.svg" alt="VK" style="width: 16px; height: 16px" />
              <span>{{ typeLabel(data.channel_type) }}</span>
            </div>
          </template>
        </PColumn>
        <PColumn header="Статус">
          <template #body="{ data }">
            <div style="display: flex; align-items: center; gap: 6px">
              <PTag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" />
              <span v-if="data.status_detail" style="font-size: 0.75em; color: var(--text-muted)" :title="data.status_detail">ⓘ</span>
            </div>
          </template>
        </PColumn>
        <PColumn header="Автолид">
          <template #body="{ data }">
            <span :style="{ color: data.auto_create_lead ? '#16a34a' : 'var(--text-muted)' }">{{ data.auto_create_lead ? 'Да' : 'Нет' }}</span>
          </template>
        </PColumn>
        <PColumn header="Webhook URL">
          <template #body="{ data }">
            <code style="font-size: 0.8em; word-break: break-all; cursor: pointer" @click="$emit('copyWebhook', data)" :title="'Нажмите чтобы скопировать'">
              {{ webhookUrl(data) }}
            </code>
          </template>
        </PColumn>
        <PColumn header="Активен">
          <template #body="{ data }">
            <span :style="{ color: data.is_active ? '#059669' : '#dc2626' }">{{ data.is_active ? 'Да' : 'Нет' }}</span>
          </template>
        </PColumn>
        <PColumn header="">
          <template #body="{ data }">
            <PButton v-if="data.channel_type === 'telegram' || data.channel_type === 'max'" icon="pi pi-link" text size="small"
              @click="$emit('registerWebhook', data.id)" title="Зарегистрировать webhook" :severity="data.status === 'error' ? 'danger' : 'secondary'" />
            <PButton icon="pi pi-pencil" text size="small" @click="$emit('edit', data)" />
            <PButton icon="pi pi-power-off" text size="small" :severity="data.is_active ? 'warning' : 'success'"
              @click="$emit('toggle', data)" :title="data.is_active ? 'Деактивировать' : 'Активировать'" />
            <PButton icon="pi pi-trash" text size="small" severity="danger" @click="$emit('remove', data.id)" />
          </template>
        </PColumn>
      </PDataTable>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Presentational shell for the Channels tab (connect/edit form +
 * channels table). `form` is the parent's reactive object passed by
 * reference — v-model mutates the same proxy `submitChannel`/`startEdit`
 * read. All CRUD logic stays in the parent and is invoked via emits.
 */
export interface ChannelCredentials {
  bot_token: string
  send_url: string
  auth_token: string
  webhook_token: string
  // email-канал (IMAP/SMTP)
  imap_host: string
  imap_port: number
  imap_ssl: boolean
  smtp_host: string
  smtp_port: number
  smtp_ssl: boolean
  username: string
  password: string
  poll_folder: string
  from_name: string
}

export interface ChannelForm {
  name: string
  channel_type: string
  credentials: ChannelCredentials
  auto_create_lead: boolean
  welcome_message: string
  is_active: boolean
}

defineProps<{
  form: ChannelForm
  editingId: number | null
  channels: any[]
  typeOptions: { value: string; label: string }[]
  typeLabel: (v: string) => string
  statusLabel: (s: string) => string
  statusSeverity: (s: string) => string
  webhookUrl: (ch: any) => string
}>()

defineEmits<{
  submit: []
  cancel: []
  edit: [any]
  toggle: [any]
  remove: [number]
  registerWebhook: [number]
  copyWebhook: [any]
}>()
</script>

<style scoped>
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
</style>
