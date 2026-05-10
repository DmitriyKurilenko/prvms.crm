<template>
  <section class="team-page animate-fade">
    <div class="section-header">
      <h1 class="page-title">Команда</h1>
    </div>

    <div class="tab-bar">
      <PButton label="Участники" :outlined="activeTab !== 'members'" @click="activeTab = 'members'" size="small" />
      <PButton label="Менеджеры" :outlined="activeTab !== 'managers'" @click="activeTab = 'managers'; loadManagers()" size="small" />
      <PButton label="Права ролей" :outlined="activeTab !== 'permissions'" @click="activeTab = 'permissions'; loadRolePermissions()" size="small" />
    </div>

    <!-- ═══ MEMBERS TAB ═══ -->
    <template v-if="activeTab === 'members'">
      <div class="surface-card" style="padding: 16px">
        <h3>Пригласить пользователя</h3>
        <form @submit.prevent="invite" style="display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; align-items: flex-end">
          <PInputText v-model="email" placeholder="email@example.com" style="min-width: 220px" />
          <PSelect v-model="inviteRole" :options="roleOptions" optionLabel="label" optionValue="value" placeholder="Роль" style="min-width: 160px" />
          <PButton type="submit" label="Пригласить" icon="pi pi-send" :disabled="!email.trim()" />
        </form>

        <!-- invite link result -->
        <div v-if="lastInviteLink" class="invite-link-box">
          <div style="font-weight: 600; margin-bottom: 4px">Ссылка-приглашение:</div>
          <div style="display: flex; gap: 8px; align-items: center">
            <code style="word-break: break-all; flex: 1; font-size: 0.85em">{{ lastInviteLink }}</code>
            <PButton icon="pi pi-copy" text size="small" @click="copyLink(lastInviteLink)" title="Скопировать ссылку" />
          </div>
          <small style="color: var(--text-muted)">Отправьте эту ссылку приглашённому. Действительна 48 часов.</small>
        </div>
      </div>

      <div class="surface-card" style="padding: 16px; margin-top: 14px">
        <PDataTable :value="users" :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]" size="small" stripedRows>
          <PColumn field="email" header="Email" />
          <PColumn field="username" header="Имя" />
          <PColumn header="Роль">
            <template #body="{ data }">
              <PSelect v-if="data.status !== 'pending'" v-model="data.role" :options="roleOptions" optionLabel="label" optionValue="value"
                style="min-width: 130px" @change="updateRole(data.id, data.role)" />
              <span v-else>{{ roleLabel(data.role) }}</span>
            </template>
          </PColumn>
          <PColumn header="Статус">
            <template #body="{ data }">
              <PTag v-if="data.status === 'pending'" value="Ожидает" severity="warning" />
              <PTag v-else value="Активен" severity="success" />
            </template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <template v-if="data.status === 'pending'">
                <PButton icon="pi pi-copy" text size="small" @click="copyLink(data.invite_link)" title="Скопировать ссылку" />
                <PButton icon="pi pi-refresh" text size="small" @click="resendInvite(data.id)" title="Переслать приглашение" />
                <PButton icon="pi pi-times" text size="small" severity="danger" @click="deactivateUser(data.id)" title="Отменить приглашение" />
              </template>
              <template v-else>
                <PButton icon="pi pi-trash" text size="small" severity="danger" @click="deactivateUser(data.id)" title="Деактивировать" />
              </template>
            </template>
          </PColumn>
        </PDataTable>
      </div>
    </template>

    <!-- ═══ MANAGERS TAB ═══ -->
    <template v-if="activeTab === 'managers'">
      <div class="surface-card" style="padding: 16px">
        <PDataTable :value="managers" :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]" size="small" stripedRows>
          <PColumn field="name" header="Менеджер" />
          <PColumn field="email" header="Email" />
          <PColumn header="Макс. сделок" style="width: 130px">
            <template #body="{ data }">{{ data.max_active_deals }}</template>
          </PColumn>
          <PColumn header="Расписание">
            <template #body="{ data }">
              <span v-if="Object.keys(data.schedule || {}).length" style="font-size: 0.85em">
                {{ scheduleLabel(data.schedule) }}
              </span>
              <span v-else style="color: var(--text-muted); font-size: 0.85em">Не задано</span>
            </template>
          </PColumn>
          <PColumn header="Выходные">
            <template #body="{ data }">
              <span style="font-size: 0.85em">{{ data.days_off?.length || 0 }} дн.</span>
            </template>
          </PColumn>
          <PColumn header="" style="width: 80px">
            <template #body="{ data }">
              <PButton icon="pi pi-pencil" text size="small" @click="startEditManager(data)" title="Настроить" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- Edit manager dialog -->
      <PDialog v-model:visible="editDialogVisible" :header="editingManager?.name || 'Менеджер'" modal style="width: 520px">
        <template v-if="editingManager">
          <div style="display: flex; flex-direction: column; gap: 14px">
            <div>
              <label class="field-label">Макс. одновременных сделок</label>
              <PInputNumber v-model="editForm.max_active_deals" :min="1" :max="999" style="width: 100%" />
            </div>

            <div>
              <label class="field-label">Рабочие дни</label>
              <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px">
                <PButton v-for="(dayLabel, dayKey) in weekDays" :key="dayKey"
                  :label="dayLabel" size="small"
                  :outlined="!editForm.schedule.working_days?.includes(dayKey)"
                  @click="toggleWorkingDay(dayKey)" />
              </div>
            </div>

            <div style="display: flex; gap: 12px">
              <div style="flex: 1">
                <label class="field-label">Начало</label>
                <PInputText v-model="editForm.schedule.start_time" placeholder="09:00" style="width: 100%" />
              </div>
              <div style="flex: 1">
                <label class="field-label">Конец</label>
                <PInputText v-model="editForm.schedule.end_time" placeholder="18:00" style="width: 100%" />
              </div>
            </div>

            <div>
              <label class="field-label" style="margin-bottom: 6px; display: block">Выходные / отпуска</label>
              <div v-for="d in editingManager.days_off" :key="d.id" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 0.9em">
                <span>{{ d.date }}</span>
                <span style="color: var(--text-muted)">{{ d.reason }}</span>
                <PButton icon="pi pi-times" text size="small" severity="danger" @click="removeDayOff(d.id)" />
              </div>
              <div style="display: flex; gap: 8px; align-items: flex-end; margin-top: 6px">
                <PInputText v-model="newDayOff.date" placeholder="2026-05-01" style="width: 140px" />
                <PInputText v-model="newDayOff.reason" placeholder="Причина" style="flex: 1" />
                <PButton icon="pi pi-plus" size="small" @click="addDayOff" :disabled="!newDayOff.date" />
              </div>
            </div>
          </div>

          <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
            <PButton label="Отмена" text @click="editDialogVisible = false" />
            <PButton label="Сохранить" @click="saveManager" />
          </div>
        </template>
      </PDialog>
    </template>

    <!-- ═══ ROLE PERMISSIONS TAB ═══ -->
    <template v-if="activeTab === 'permissions'">
      <div class="surface-card" style="padding: 16px">
        <h3 style="margin-top: 0;">Права ролей CRM</h3>
        <p style="margin-top: 0; color: var(--text-muted);">
          Настройка прав для сущностей «Сделки», «Контакты», «Компании»: просмотр, создание, редактирование, удаление и область видимости.
        </p>
        <PDataTable :value="permissionRows" size="small" stripedRows :loading="permissionsLoading">
          <PColumn field="role_label" header="Роль" />
          <PColumn field="entity_label" header="Сущность" />
          <PColumn header="Просмотр" style="width: 110px">
            <template #body="{ data }">
              <input type="checkbox" v-model="data.can_view" @change="onViewToggle(data)" />
            </template>
          </PColumn>
          <PColumn header="Создание" style="width: 110px">
            <template #body="{ data }">
              <input type="checkbox" v-model="data.can_create" @change="onWriteToggle(data)" />
            </template>
          </PColumn>
          <PColumn header="Редакт." style="width: 110px">
            <template #body="{ data }">
              <input type="checkbox" v-model="data.can_update" @change="onWriteToggle(data)" />
            </template>
          </PColumn>
          <PColumn header="Удаление" style="width: 110px">
            <template #body="{ data }">
              <input type="checkbox" v-model="data.can_delete" @change="onWriteToggle(data)" />
            </template>
          </PColumn>
          <PColumn header="Область" style="width: 170px">
            <template #body="{ data }">
              <PSelect
                v-model="data.scope"
                :options="scopeOptions"
                optionLabel="label"
                optionValue="value"
                style="min-width: 130px"
              />
            </template>
          </PColumn>
          <PColumn header="" style="width: 120px">
            <template #body="{ data }">
              <PButton label="Сохранить" size="small" @click="saveRolePermission(data)" />
            </template>
          </PColumn>
        </PDataTable>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/http'

/* ── state ── */
const toast = useToast()
const users = ref<any[]>([])
const email = ref('')
const inviteRole = ref('manager')
const lastInviteLink = ref('')
const managers = ref<any[]>([])
const editDialogVisible = ref(false)
const editingManager = ref<any>(null)
const editForm = reactive({ max_active_deals: 10, schedule: {} as Record<string, any> })
const newDayOff = reactive({ date: '', reason: '' })
const permissionsLoading = ref(false)
const permissionRows = ref<Array<{
  role: string
  role_label: string
  entity: string
  entity_label: string
  can_view: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
  scope: string
}>>([])
const scopeValues = ref<string[]>(['all', 'team', 'own'])

const roleOptions = [
  { value: 'owner', label: 'Владелец' },
  { value: 'admin', label: 'Администратор' },
  { value: 'manager', label: 'Менеджер' },
  { value: 'viewer', label: 'Наблюдатель' },
]

const entityLabels: Record<string, string> = {
  deals: 'Сделки',
  contacts: 'Контакты',
  companies: 'Компании',
}

const scopeLabels: Record<string, string> = {
  all: 'Все',
  team: 'Команда',
  own: 'Только свои',
}

const scopeOptions = computed(() => scopeValues.value.map((value) => ({ value, label: scopeLabels[value] || value })))

const weekDays: Record<string, string> = {
  mon: 'Пн', tue: 'Вт', wed: 'Ср', thu: 'Чт', fri: 'Пт', sat: 'Сб', sun: 'Вс',
}

/* ── members ── */
const load = async () => {
  users.value = await api('/users/')
}

const invite = async () => {
  const res = await api('/users/invite', { method: 'POST', body: { email: email.value, role: inviteRole.value } })
  lastInviteLink.value = res.invite_link || ''
  email.value = ''
  await load()
}

const resendInvite = async (userId: number) => {
  const res = await api(`/users/${userId}/resend-invite`, { method: 'POST' })
  lastInviteLink.value = res.invite_link || ''
}

const copyLink = (link: string) => {
  navigator.clipboard.writeText(link)
}

const roleLabel = (value: string) => {
  return roleOptions.find(o => o.value === value)?.label || value
}

const updateRole = async (userId: number, newRole: string) => {
  await api(`/users/${userId}/role`, { method: 'PATCH', body: { role: newRole } })
}

const deactivateUser = async (userId: number) => {
  await api(`/users/${userId}`, { method: 'DELETE' })
  await load()
}

/* ── managers ── */
const loadManagers = async () => {
  managers.value = await api('/users/managers/')
}

const startEditManager = (m: any) => {
  editingManager.value = m
  editForm.max_active_deals = m.max_active_deals
  editForm.schedule = { ...m.schedule }
  if (!editForm.schedule.working_days) editForm.schedule.working_days = []
  editDialogVisible.value = true
}

const toggleWorkingDay = (day: string) => {
  if (!editForm.schedule.working_days) editForm.schedule.working_days = []
  const idx = editForm.schedule.working_days.indexOf(day)
  if (idx >= 0) editForm.schedule.working_days.splice(idx, 1)
  else editForm.schedule.working_days.push(day)
}

const saveManager = async () => {
  await api(`/users/managers/${editingManager.value.id}/`, {
    method: 'PATCH',
    body: { max_active_deals: editForm.max_active_deals, schedule: editForm.schedule },
  })
  editDialogVisible.value = false
  await loadManagers()
}

const addDayOff = async () => {
  if (!newDayOff.date || !editingManager.value) return
  const result = await api(`/users/managers/${editingManager.value.id}/days-off/`, {
    method: 'POST',
    body: { date: newDayOff.date, reason: newDayOff.reason },
  })
  editingManager.value.days_off.push(result)
  newDayOff.date = ''
  newDayOff.reason = ''
}

const removeDayOff = async (id: number) => {
  await api(`/users/managers/days-off/${id}/`, { method: 'DELETE' })
  editingManager.value.days_off = editingManager.value.days_off.filter((d: any) => d.id !== id)
}

const scheduleLabel = (s: Record<string, any>) => {
  const days = (s.working_days || []).map((d: string) => weekDays[d] || d).join(', ')
  const time = s.start_time && s.end_time ? `${s.start_time}–${s.end_time}` : ''
  return [days, time].filter(Boolean).join(' · ') || 'Настроено'
}

/* ── role permissions ── */
const loadRolePermissions = async () => {
  permissionsLoading.value = true
  try {
    const response = await api<{
      roles: Record<string, Record<string, Record<string, unknown>>>
      entities: string[]
      scopes: string[]
    }>('/users/role-permissions/')
    const entities = response.entities?.length ? response.entities : ['deals', 'contacts', 'companies']
    scopeValues.value = response.scopes?.length ? response.scopes : ['all', 'team', 'own']

    const rows: Array<{
      role: string
      role_label: string
      entity: string
      entity_label: string
      can_view: boolean
      can_create: boolean
      can_update: boolean
      can_delete: boolean
      scope: string
    }> = []

    for (const role of roleOptions) {
      const byEntity = response.roles?.[role.value] || {}
      for (const entity of entities) {
        const permission = byEntity[entity] || {}
        rows.push({
          role: role.value,
          role_label: role.label,
          entity,
          entity_label: entityLabels[entity] || entity,
          can_view: Boolean(permission.can_view),
          can_create: Boolean(permission.can_create),
          can_update: Boolean(permission.can_update),
          can_delete: Boolean(permission.can_delete),
          scope: String(permission.scope || 'all'),
        })
      }
    }

    permissionRows.value = rows
  } catch {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить права ролей.', life: 5000 })
  } finally {
    permissionsLoading.value = false
  }
}

const onViewToggle = (row: {
  can_view: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
}) => {
  if (!row.can_view) {
    row.can_create = false
    row.can_update = false
    row.can_delete = false
  }
}

const onWriteToggle = (row: {
  can_view: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
}) => {
  if (row.can_create || row.can_update || row.can_delete) {
    row.can_view = true
  }
}

const saveRolePermission = async (row: {
  role: string
  entity: string
  can_view: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
  scope: string
}) => {
  const response = await api<{ permission?: Record<string, unknown> }>(
    `/users/role-permissions/${row.role}/${row.entity}/`,
    {
      method: 'PATCH',
      body: {
        can_view: row.can_view,
        can_create: row.can_create,
        can_update: row.can_update,
        can_delete: row.can_delete,
        scope: row.scope,
      },
    }
  )
  if (response.permission) {
    row.can_view = Boolean(response.permission.can_view)
    row.can_create = Boolean(response.permission.can_create)
    row.can_update = Boolean(response.permission.can_update)
    row.can_delete = Boolean(response.permission.can_delete)
    row.scope = String(response.permission.scope || row.scope)
  }
}

/* ── init ── */
onMounted(load)
</script>

<style scoped>
.team-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.tab-bar {
  display: flex;
  gap: 8px;
}

.invite-link-box {
  margin-top: 12px;
  padding: 12px;
  background: var(--primary-lighter);
  border-radius: 8px;
  font-size: 0.9em;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}
</style>
