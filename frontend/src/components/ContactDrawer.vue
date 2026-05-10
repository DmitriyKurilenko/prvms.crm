<template>
  <PDrawer
    v-model:visible="visible"
    position="right"
    :style="{ width: '520px' }"
    :pt="{ root: { class: 'contact-drawer-root' } }"
  >
    <template #header>
      <div v-if="contact" class="drawer-header">
        <div class="avatar avatar-lg" :style="{ background: avatarColor }">{{ initials }}</div>
        <div class="drawer-header-info">
          <div class="drawer-name">{{ contact.first_name }} {{ contact.last_name }}</div>
          <div class="drawer-sub">{{ contact.position || 'Контакт' }}</div>
        </div>
        <div class="drawer-actions">
          <button class="drawer-action-btn" title="Позвонить" @click="callContact">
            <i class="pi pi-phone" />
          </button>
          <button class="drawer-action-btn" title="Написать" @click="messageContact">
            <i class="pi pi-send" />
          </button>
        </div>
      </div>
    </template>

    <div v-if="contact" class="drawer-body">
      <!-- Tabs -->
      <div class="drawer-tabs">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="drawer-tab"
          :class="{ active: activeTab === t.id }"
          @click="activeTab = t.id"
        >{{ t.label }}</button>
      </div>

      <!-- Info tab -->
      <div v-if="activeTab === 'info'" class="tab-pane animate-fade">
        <div class="info-grid">
          <div class="info-row">
            <i class="pi pi-envelope info-icon" />
            <div>
              <div class="info-label">Email</div>
              <div class="info-val">{{ contact.email || '—' }}</div>
            </div>
          </div>
          <div class="info-row">
            <i class="pi pi-phone info-icon" />
            <div>
              <div class="info-label">Телефон</div>
              <div class="info-val">{{ contact.phone || '—' }}</div>
            </div>
          </div>
          <div class="info-row">
            <i class="pi pi-building info-icon" />
            <div>
              <div class="info-label">Компания</div>
              <div class="info-val">{{ companyName || '—' }}</div>
            </div>
          </div>
          <div class="info-row">
            <i class="pi pi-id-card info-icon" />
            <div>
              <div class="info-label">Должность</div>
              <div class="info-val">{{ contact.position || '—' }}</div>
            </div>
          </div>
          <div v-if="contact.messenger_id" class="info-row">
            <i class="pi pi-telegram info-icon" />
            <div>
              <div class="info-label">Мессенджер</div>
              <div class="info-val">{{ contact.messenger_id }}</div>
            </div>
          </div>
          <div class="info-row">
            <i class="pi pi-calendar info-icon" />
            <div>
              <div class="info-label">Создан</div>
              <div class="info-val">{{ formatDate(contact.created_at) }}</div>
            </div>
          </div>
          <div v-if="contact.esign_agreement_signed_at" class="info-row">
            <i class="pi pi-verified info-icon" style="color: #22c55e" />
            <div>
              <div class="info-label">ЭДО</div>
              <div class="info-val" style="color: #22c55e">✅ Соглашение подписано</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Activity tab -->
      <div v-if="activeTab === 'activity'" class="tab-pane animate-fade">
        <div v-if="contact.activities?.length" class="activity-timeline">
          <div v-for="a in contact.activities" :key="a.id" class="tl-item">
            <div class="tl-dot" :class="a.type" />
            <div class="tl-line" />
            <div class="tl-card">
              <div class="tl-title">{{ a.title }}</div>
              <div class="tl-meta">
                <PTag :value="activityLabel(a.type)" size="small" />
                <span class="tl-date">{{ formatDateTime(a.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">Нет активностей</div>
      </div>

      <!-- Notes tab -->
      <div v-if="activeTab === 'notes'" class="tab-pane animate-fade">
        <div class="notes-area">
          <PTextarea v-model="noteText" rows="4" placeholder="Введите заметку..." class="w-full" autoResize />
          <PButton label="Сохранить заметку" :disabled="!noteText.trim()" @click="saveNote" />
        </div>
      </div>
    </div>
  </PDrawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CrmContact, CrmActivity } from '@/api/crm'
import * as crmApi from '@/api/crm'
import { formatDate, formatDateTime } from '@/utils/datetime'

const props = defineProps<{
  modelValue: boolean
  contactId: number | null
  companies?: { id: number; name: string }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  updated: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const contact = ref<(CrmContact & { activities: CrmActivity[] }) | null>(null)
const activeTab = ref('info')
const noteText = ref('')

const tabs = [
  { id: 'info', label: 'Инфо' },
  { id: 'activity', label: 'Активность' },
  { id: 'notes', label: 'Заметки' },
]

watch(() => props.contactId, async (id) => {
  if (id) {
    contact.value = await crmApi.getContact(id)
  } else {
    contact.value = null
  }
}, { immediate: true })

const initials = computed(() => {
  if (!contact.value) return '?'
  return ((contact.value.first_name?.charAt(0) || '') + (contact.value.last_name?.charAt(0) || '')).toUpperCase()
})

const avatarColors = ['#4f46e5', '#7c3aed', '#db2777', '#dc2626', '#ea580c', '#16a34a', '#0891b2', '#0284c7']
const avatarColor = computed(() => avatarColors[(contact.value?.id || 0) % avatarColors.length])

const companyName = computed(() => {
  if (!contact.value?.company_id || !props.companies) return ''
  return props.companies.find(c => c.id === contact.value!.company_id)?.name || ''
})

const activityLabel = (type: string) => ({
  call: 'Звонок', message: 'Сообщение', task: 'Задача', note: 'Заметка',
  email: 'Email', contract: 'Договор', stage_change: 'Смена стадии', system: 'Система'
}[type] || type)

const callContact = () => {
  if (contact.value?.phone) window.location.href = `tel:${contact.value.phone}`
}
const messageContact = () => { /* open chat or messenger */ }

const saveNote = async () => {
  if (!contact.value || !noteText.value.trim()) return
  await crmApi.createActivity({ activity_type: 'note', contact_id: contact.value.id, title: noteText.value.trim() })
  noteText.value = ''
  contact.value = await crmApi.getContact(contact.value.id)
  emit('updated')
}
</script>

<style scoped>
.drawer-header {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
}

.drawer-header-info {
  flex: 1;
  min-width: 0;
}

.drawer-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--text);
}

.drawer-sub {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}

.drawer-actions {
  display: flex;
  gap: 6px;
}

.drawer-action-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}

.drawer-action-btn:hover {
  background: var(--primary-lighter);
  border-color: var(--brand);
  color: var(--brand);
}

.drawer-body {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Tabs */
.drawer-tabs {
  display: flex;
  border-bottom: 2px solid var(--line);
  margin-bottom: 20px;
}

.drawer-tab {
  padding: 10px 16px;
  border: none;
  background: transparent;
  font-family: 'Nunito Sans', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.15s;
}

.drawer-tab.active {
  color: var(--brand);
  border-bottom-color: var(--brand);
}

.tab-pane {
  flex: 1;
}

/* Info grid */
.info-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}

.info-row:last-child {
  border-bottom: none;
}

.info-icon {
  font-size: 16px;
  color: var(--text-muted);
  margin-top: 2px;
  flex-shrink: 0;
  width: 18px;
}

.info-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 2px;
}

.info-val {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

/* Activity timeline */
.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tl-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  position: relative;
}

.tl-dot {
  width: 10px;
  height: 10px;
  min-width: 10px;
  border-radius: 50%;
  margin-top: 6px;
  background: var(--brand);
}

.tl-dot.call { background: #22c55e; }
.tl-dot.email { background: #3b82f6; }
.tl-dot.note { background: #f97316; }
.tl-dot.task { background: var(--brand); }

.tl-card {
  flex: 1;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}

.tl-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}

.tl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tl-date {
  font-size: 12px;
  color: var(--text-muted);
}

/* Notes */
.notes-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.w-full { width: 100%; }

.empty-state {
  color: var(--text-muted);
  padding: 24px;
  text-align: center;
}
</style>
