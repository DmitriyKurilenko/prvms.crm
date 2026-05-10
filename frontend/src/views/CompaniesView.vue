<template>
  <FeatureGate feature="crm_builtin">
    <section class="companies-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Компании</h1>
      </div>

      <div v-if="!canViewCompanies" class="surface-card" style="padding: 14px;">
        У вас нет прав для просмотра компаний.
      </div>

      <template v-else>
        <div class="toolbar">
          <PInputText v-model="search" placeholder="Поиск по названию/ИНН" @keyup.enter="load" />
          <PButton v-if="canCreateCompany" label="Новая компания" icon="pi pi-plus" size="small" @click="openCreate" />
        </div>

        <div class="surface-card" style="padding: 12px; margin-top: 12px;">
          <PDataTable
            :value="companies"
            size="small"
            stripedRows
            :paginator="true"
            :rows="20"
            :rowsPerPageOptions="[10, 20, 50]"
          >
            <PColumn field="name" header="Название" />
            <PColumn field="inn" header="ИНН" />
            <PColumn field="phone" header="Телефон" />
            <PColumn field="email" header="Email" />
            <PColumn header="" style="width: 110px">
              <template #body="{ data }">
                <PButton v-if="canUpdateCompany" icon="pi pi-pencil" text size="small" @click="openEdit(data)" />
                <PButton v-if="canDeleteCompany" icon="pi pi-trash" text size="small" severity="danger" @click="remove(data.id)" />
              </template>
            </PColumn>
            <template #empty>
              <div class="empty-state">Нет компаний</div>
            </template>
          </PDataTable>
        </div>
      </template>

      <PDialog v-model:visible="dialogVisible" :header="form.id ? 'Редактирование компании' : 'Новая компания'" :style="{ width: '450px' }" modal>
        <div class="form-grid">
          <PInputText v-model="form.name" placeholder="Название" />
          <PInputText v-model="form.inn" placeholder="ИНН" />
          <PInputText v-model="form.phone" placeholder="Телефон" />
          <PInputText v-model="form.email" placeholder="Email" />
          <PButton
            :label="form.id ? 'Сохранить' : 'Создать'"
            :disabled="!form.name || (form.id ? !canUpdateCompany : !canCreateCompany)"
            @click="submit"
          />
        </div>
      </PDialog>
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
import type { CrmCompany } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('companies')
const toast = useToast()
const authStore = useAuthStore()
const crmPermissions = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canViewCompanies = computed(() => crmPermissions.value.companies.can_view)
const canCreateCompany = computed(() => crmPermissions.value.companies.can_create)
const canUpdateCompany = computed(() => crmPermissions.value.companies.can_update)
const canDeleteCompany = computed(() => crmPermissions.value.companies.can_delete)

const companies = ref<CrmCompany[]>([])
const search = ref('')
const dialogVisible = ref(false)
const form = reactive({
  id: null as number | null,
  name: '',
  inn: '',
  phone: '',
  email: '',
})

function resetForm() {
  form.id = null
  form.name = ''
  form.inn = ''
  form.phone = ''
  form.email = ''
}

async function load() {
  if (!canViewCompanies.value) {
    companies.value = []
    return
  }
  try {
    companies.value = await crmApi.listCompanies(search.value || undefined)
  } catch (err) {
    log.error('Failed to load companies', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить список компаний', life: 5000 })
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(c: CrmCompany) {
  form.id = c.id
  form.name = c.name
  form.inn = c.inn
  form.phone = c.phone
  form.email = c.email
  dialogVisible.value = true
}

async function submit() {
  if (!form.name) return
  const allowed = form.id ? canUpdateCompany.value : canCreateCompany.value
  if (!allowed) return
  const payload = { name: form.name, inn: form.inn, phone: form.phone, email: form.email }
  try {
    if (form.id) {
      await crmApi.patchCompany(form.id, payload)
    } else {
      await crmApi.createCompany(payload)
    }
    dialogVisible.value = false
    resetForm()
    await load()
  } catch (err) {
    log.error('Failed to save company', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить компанию', life: 5000 })
  }
}

async function remove(id: number) {
  if (!canDeleteCompany.value) return
  try {
    await crmApi.deleteCompany(id)
    await load()
  } catch (err) {
    log.error('Failed to delete company', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить компанию', life: 5000 })
  }
}

onMounted(load)
</script>

<style scoped>
.companies-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.empty-state { padding: 18px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
