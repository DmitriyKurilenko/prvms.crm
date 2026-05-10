<template>
  <FeatureGate feature="crm_builtin" class="view-gate">
    <section class="contacts-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Контакты</h1>
        <PButton
          v-if="canCreateContact"
          label="Новый контакт"
          icon="pi pi-plus"
          size="small"
          @click="openCreateForm"
        />
      </div>

      <!-- Toolbar -->
      <div class="contacts-toolbar">
        <div class="search-field-wrap">
          <i class="pi pi-search" />
          <input
            v-model="contactSearch"
            class="search-field"
            type="text"
            placeholder="Поиск по имени, телефону..."
            @keyup.enter="loadContacts"
          />
        </div>
        <PButton icon="pi pi-refresh" size="small" outlined @click="loadContacts" />
      </div>

      <!-- Table -->
      <div class="surface-card contacts-table-wrap">
        <PDataTable
          :value="contacts"
          size="small"
          stripedRows
          :paginator="contacts.length > 20"
          :rows="20"
          :rowsPerPageOptions="[10, 20, 50]"
          :loading="loading"
          class="contacts-table"
        >
          <PColumn field="first_name" header="Контакт" sortable>
            <template #body="{ data }">
              <div class="contact-cell" @click="openDetail(data.id)">
                <div class="contact-avatar avatar avatar-sm">
                  {{ avatarLetters(data) }}
                </div>
                <div>
                  <div class="contact-name">{{ data.first_name }} {{ data.last_name }}</div>
                  <div class="contact-email">{{ data.email || '—' }}</div>
                </div>
              </div>
            </template>
          </PColumn>
          <PColumn field="phone" header="Телефон" />
          <PColumn header="Компания">
            <template #body="{ data }">
              {{ companyName(data.company_id) || '—' }}
            </template>
          </PColumn>
          <PColumn header="ЭДО">
            <template #body="{ data }">
              <span v-if="(data as any).esign_agreement_signed_at" class="esign-ok" title="Соглашение подписано">✅</span>
              <span v-else class="esign-no">—</span>
            </template>
          </PColumn>
          <PColumn header="" style="width: 100px">
            <template #body="{ data }">
              <div class="row-actions">
                <button class="row-btn" title="Открыть" @click="openDetail(data.id)"><i class="pi pi-eye" /></button>
                <button v-if="canUpdateContact" class="row-btn" title="Редактировать" @click="editContact(data)"><i class="pi pi-pencil" /></button>
                <button v-if="canDeleteContact" class="row-btn row-btn-danger" title="Удалить" @click="removeContact(data.id)"><i class="pi pi-trash" /></button>
              </div>
            </template>
          </PColumn>
          <template #empty>
            <div class="empty-state">Контактов не найдено</div>
          </template>
        </PDataTable>
      </div>

      <!-- Contact Detail Drawer -->
      <ContactDrawer
        v-model="showDetail"
        :contact-id="selectedContactId"
        :companies="companies"
        @updated="loadContacts"
      />

      <!-- Contact Form -->
      <PDialog
        v-model:visible="showForm"
        :header="contactForm.id ? 'Редактировать контакт' : 'Новый контакт'"
        :style="{ width: '500px', maxWidth: '95vw' }"
        modal
      >
        <div class="form-grid">
          <div class="form-row-2">
            <div>
              <label class="field-label">Имя *</label>
              <PInputText v-model="contactForm.first_name" placeholder="Имя" class="w-full" />
            </div>
            <div>
              <label class="field-label">Фамилия</label>
              <PInputText v-model="contactForm.last_name" placeholder="Фамилия" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Телефон</label>
              <PInputText v-model="contactForm.phone" placeholder="+7 (___) ___-__-__" class="w-full" />
            </div>
            <div>
              <label class="field-label">Email</label>
              <PInputText v-model="contactForm.email" placeholder="email@example.com" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Должность</label>
              <PInputText v-model="contactForm.position" placeholder="Менеджер, директор..." class="w-full" />
            </div>
            <div>
              <label class="field-label">Компания</label>
              <PSelect
                v-model="contactForm.company_id"
                :options="companyOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="— не выбрана —"
                showClear
                filter
                filterPlaceholder="Поиск…"
                class="w-full"
              />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Мессенджер</label>
              <PInputText v-model="contactForm.messenger_id" placeholder="Telegram, WhatsApp..." class="w-full" />
            </div>
            <div>
              <label class="field-label">Источник</label>
              <PSelect
                v-model="contactForm.source"
                :options="sourceOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="— не указан —"
                showClear
                class="w-full"
              />
            </div>
          </div>
          <div>
            <label class="field-label">Ответственный</label>
            <PSelect
              v-model="contactForm.responsible_id"
              :options="managerOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="— не выбран —"
              showClear
              class="w-full"
            />
          </div>
          <PButton
            :label="contactForm.id ? 'Сохранить' : 'Создать'"
            :disabled="!contactForm.first_name"
            @click="submitContact"
          />
        </div>
      </PDialog>
    </section>

    <template #locked>
      <div class="surface-card" style="padding: 16px">Раздел доступен в плане CRM.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import ContactDrawer from '@/components/ContactDrawer.vue'
import * as crmApi from '@/api/crm'
import type { CrmContact } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const auth = useAuthStore()
const toast = useToast()
const perms = computed(() => normalizeCrmPermissions(auth.user?.crm_permissions))
const canCreateContact = computed(() => perms.value.contacts.can_create)
const canUpdateContact = computed(() => perms.value.contacts.can_update)
const canDeleteContact = computed(() => perms.value.contacts.can_delete)

const sourceOptions = [
  { label: 'Сайт', value: 'website' },
  { label: 'Телефон', value: 'phone' },
  { label: 'Email', value: 'email' },
  { label: 'Соцсети', value: 'social' },
  { label: 'Рекомендация', value: 'referral' },
  { label: 'Реклама', value: 'ad' },
  { label: 'Другое', value: 'other' },
]

/* --- Data --- */
const contacts = ref<CrmContact[]>([])
const companies = ref<crmApi.CrmCompany[]>([])
const managers = ref<{ id: number; name: string }[]>([])
const loading = ref(false)
const contactSearch = ref('')
const selectedContactId = ref<number | null>(null)

const companyOptions = computed(() => companies.value.map(c => ({ label: c.name, value: c.id })))
const managerOptions = computed(() => managers.value.map(m => ({ label: m.name, value: m.id })))
const companyName = (id: number | null) => companies.value.find(c => c.id === id)?.name || ''

const loadContacts = async () => {
  loading.value = true
  try {
    contacts.value = await crmApi.listContacts(contactSearch.value || undefined)
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить контакты.', life: 5000 })
  }
  loading.value = false
}

onMounted(async () => {
  await Promise.all([
    loadContacts(),
    crmApi.listCompanies().then(r => (companies.value = r)),
    crmApi.listManagers().then(r => (managers.value = r)),
  ])
})

/* --- Detail --- */
const showDetail = ref(false)

const openDetail = (id: number) => {
  selectedContactId.value = id
  showDetail.value = true
}

/* --- Form --- */
const showForm = ref(false)
const contactForm = reactive({
  id: null as number | null,
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  position: '',
  company_id: null as number | null,
  messenger_id: '',
  source: '',
  responsible_id: null as number | null,
})

const openCreateForm = () => {
  Object.assign(contactForm, { id: null, first_name: '', last_name: '', phone: '', email: '', position: '', company_id: null, messenger_id: '', source: '', responsible_id: null })
  showForm.value = true
}

const editContact = (c: CrmContact) => {
  Object.assign(contactForm, {
    id: c.id,
    first_name: c.first_name,
    last_name: c.last_name,
    phone: c.phone,
    email: c.email,
    position: (c as any).position || '',
    company_id: c.company_id,
    messenger_id: (c as any).messenger_id || '',
    source: (c as any).source || '',
    responsible_id: c.responsible_id,
  })
  showForm.value = true
}

const submitContact = async () => {
  if (!contactForm.first_name) return
  const data = {
    first_name: contactForm.first_name,
    last_name: contactForm.last_name,
    phone: contactForm.phone,
    email: contactForm.email,
    position: contactForm.position,
    company_id: contactForm.company_id,
    messenger_id: contactForm.messenger_id,
    source: contactForm.source,
    responsible_id: contactForm.responsible_id,
  }
  try {
    if (contactForm.id) {
      await crmApi.patchContact(contactForm.id, data)
    } else {
      await crmApi.createContact(data)
    }
    showForm.value = false
    await loadContacts()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить контакт.', life: 5000 })
  }
}

const removeContact = async (id: number) => {
  if (!canDeleteContact.value) return
  try {
    await crmApi.deleteContact(id)
    await loadContacts()
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить контакт.', life: 5000 })
  }
}

/* --- Helpers --- */
const avatarLetters = (c: CrmContact) => {
  const first = c.first_name?.charAt(0) || ''
  const last = c.last_name?.charAt(0) || ''
  return (first + last).toUpperCase() || '?'
}
</script>

<style scoped>
.view-gate,
:deep(.view-gate > div) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.contacts-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.contacts-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-field-wrap {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 380px;
}

.search-field-wrap .pi {
  position: absolute;
  left: 10px;
  color: var(--text-muted);
  font-size: 13px;
  pointer-events: none;
}

.search-field {
  width: 100%;
  padding: 8px 12px 8px 32px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  font-family: 'Nunito Sans', sans-serif;
  outline: none;
}

.search-field:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.contacts-table-wrap {
  flex: 1;
  overflow: auto;
}

.contact-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.contact-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}

.contact-email {
  font-size: 12px;
  color: var(--text-muted);
}

.contact-avatar {
  background: var(--brand);
}

.row-actions {
  display: flex;
  gap: 2px;
}

.row-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
}

.row-btn:hover {
  background: var(--surface-alt);
  color: var(--text);
}

.row-btn-danger:hover {
  background: #fef2f2;
  color: var(--danger);
}

.esign-ok { color: #22c55e; }
.esign-no { color: var(--text-muted); }

/* Detail dialog */
.detail-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 4px;
}

.detail-name {
  font-size: 18px;
  font-weight: 700;
}

.detail-sub {
  font-size: 13px;
  color: var(--text-muted);
}

/* Activity */
.activity-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.activity-section h4 {
  font-size: 14px;
  font-weight: 700;
  margin: 0;
}

.activity-list {
  max-height: 220px;
  overflow-y: auto;
}

.timeline-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}

.tl-icon { font-size: 16px; flex-shrink: 0; }
.tl-content { flex: 1; min-width: 0; }
.tl-meta { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.tl-date { font-size: 12px; color: var(--text-muted); }

/* Form */
.form-grid { display: grid; gap: 12px; }
.form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: var(--text); }
.w-full { width: 100%; }
.empty-state { color: var(--text-muted); padding: 24px; text-align: center; }
</style>
